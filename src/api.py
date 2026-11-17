"""Thin HTTP layer over the existing Day 7 agent for the workbench UI (src/frontend). No RAG logic lives here.

    python -m src.api [--port 8800] [--host 127.0.0.1]   -> http://127.0.0.1:8765 by default (UI at /, API under /api)

Endpoints (all real, nothing mocked):
  GET  /api/health                        chunk count + vector-store row count (database reachability)
  GET  /api/config                        retrievers, providers (availability only: never keys), presets, chapters
  POST /api/chat                          run BookAgent once -> {trace, chunks, error_kind}
  GET  /api/pdf                           the original book_ML.pdf (open in a browser tab)
  GET  /api/pdf/page/{n}.png?scale=1.5    page rendered by PyMuPDF from the original PDF
  GET  /api/pdf/page/{n}/locate?chunk_id= exact character boxes of a chunk on its page (or found=false)

The agent, retrievers, LLM client, config dataclass and trace schema are the ones in src/agent.py, src/retrieval.py,
src/llm.py; this module only caches them (the e5 model and BM25 index are loaded once) and serialises runs with a lock.
"""
from __future__ import annotations

import functools
import os
import threading
import time
import unicodedata
import uuid
from collections import Counter
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.agent import AgentConfig, BookAgent
from src.agent_configs import CONFIGS
from src.llm import PROVIDERS, LLMClient, load_env
from src.retrieval import DAY7, check_filters, load_chunks

load_env()
FRONTEND = DAY7 / "src" / "frontend"
BOOK_PDF = Path(os.getenv("BOOK_PDF") or DAY7.parent / "book_ML.pdf")
RETRIEVERS = {
    "dense": "Dense (E5 + pgvector)",
    "bm25": "BM25 (syllables)",
    "bm25_2gram": "BM25 + syllable bigrams",
    "tfidf": "TF-IDF (starter baseline)",
    "hybrid": "Hybrid RRF (dense + BM25)",
    "hybrid_2gram": "Hybrid RRF (dense + BM25 bigram)",
}
LIMITS = {"top_k": (1, 10), "budget_chars": (300, 12000), "max_new_per_search": (1, 6),
          "max_book_searches": (1, 6), "max_steps": (2, 10)}

CHUNKS: dict[str, dict[str, Any]] = {c["id"]: c for c in load_chunks()}
app = FastAPI(title="Day 7 Agentic RAG workbench API")
_run_lock, _pdf_lock = threading.Lock(), threading.Lock()
_retrievers: dict[str, Any] = {}
_llms: dict[tuple[str, str | None], LLMClient] = {}


# --------------------------------------------------------------------------- helpers
def get_retriever(name: str):
    if name in _retrievers:
        return _retrievers[name]
    from src import retrieval as R
    chunks = list(CHUNKS.values())
    if name == "tfidf":
        from src.eval_retrieval import TfidfRetriever  # starter baseline adapter
        r = TfidfRetriever(chunks)
    elif name in ("bm25", "bm25_2gram"):
        r = R.BM25Retriever(chunks, ngram=2 if name.endswith("2gram") else 1)
    elif name == "dense":
        r = R.DenseRetriever()
    elif name in ("hybrid", "hybrid_2gram"):
        r = R.HybridRetriever(get_retriever("dense"), get_retriever("bm25_2gram" if name.endswith("2gram") else "bm25"))
    else:
        raise HTTPException(400, f"unknown retriever {name!r}")
    _retrievers[name] = r
    return r


def get_llm(provider: str | None, model: str | None) -> LLMClient:
    key = (provider or os.getenv("LLM_PROVIDER") or "openrouter", model or None)
    if key not in _llms:
        _llms[key] = LLMClient(*key)
    return _llms[key]


def classify(error: str) -> str:
    e = error or ""
    if any(s in e for s in ("AuthenticationError", "APIConnectionError", "APITimeoutError", "RateLimitError",
                            "BadRequestError", "NotFoundError", "PermissionDeniedError", "InternalServerError",
                            "_API_KEY", "unknown provider", "empty response")):
        return "provider"
    if any(s in e for s in ("psycopg", "OperationalError", "connection to server", "DATABASE_URL", "book_chunks")):
        return "database"
    if "FileNotFoundError" in e:
        return "setup"
    return "agent"


def build_config(raw: dict[str, Any]) -> AgentConfig:
    base = asdict(CONFIGS.get(raw.get("preset") or "", AgentConfig()))
    names = {f.name for f in fields(AgentConfig)}
    for k, v in raw.items():
        if k not in names or k == "name" or v is None:
            continue
        if k == "retriever":
            if v not in RETRIEVERS:
                raise HTTPException(400, f"retriever must be one of {sorted(RETRIEVERS)}")
            base[k] = v
        elif k == "external_tools":
            base[k] = bool(v)
        elif k in LIMITS:
            lo, hi = LIMITS[k]
            try:
                base[k] = max(lo, min(hi, int(v)))
            except (TypeError, ValueError):
                raise HTTPException(400, f"{k} must be an integer")
    base["name"] = "ui:" + (raw.get("preset") or "custom")
    return AgentConfig(**base)


def chunk_view(cid: str) -> dict[str, Any] | None:
    c = CHUNKS.get(cid)
    return None if c is None else {k: c[k] for k in ("id", "text", "page", "source", "source_id", "metadata")}


# --------------------------------------------------------------------------- API
@app.get("/api/health")
def health() -> dict[str, Any]:
    out: dict[str, Any] = {"chunks_json": len(CHUNKS), "pdf": BOOK_PDF.exists()}
    try:
        from src.day6_bridge import _load_day6
        import importlib
        _load_day6()
        store_mod, env_mod = importlib.import_module("day6src.book_store"), importlib.import_module("day6src.store")
        out["vector_store_rows"] = store_mod.BookStore(env_mod.database_url_from_env(), 768).count()
        out["database"] = "ok"
    except Exception as exc:
        out["database"] = f"error: {type(exc).__name__}: {str(exc)[:200]}"
    return out


@app.get("/api/config")
def config() -> dict[str, Any]:
    default_provider = (os.getenv("LLM_PROVIDER") or "openrouter").lower()
    providers = []
    for pid, cfg in PROVIDERS.items():
        has_key = cfg["key_env"] is None or bool(os.getenv(cfg["key_env"]))
        models = [cfg["model"]]
        if pid == default_provider and os.getenv("LLM_MODEL"):
            models.insert(0, os.getenv("LLM_MODEL"))
        providers.append({"id": pid, "models": list(dict.fromkeys(models)), "available": has_key,
                          "note": ("local server, not checked" if cfg["key_env"] is None
                                   else ("key configured on server" if has_key else f"{cfg['key_env']} not set on server"))})
    titles: dict[str, Counter] = {}
    first_page: dict[str, int] = {}
    for c in CHUNKS.values():
        no = c["metadata"].get("chapter_no") or ""
        titles.setdefault(no, Counter())[c["metadata"].get("chapter", "")] += 1
        first_page[no] = min(first_page.get(no, 10 ** 6), c["page"])
    chapters = [{"chapter_no": no, "title": "Lời nói đầu" if no == "0" else t.most_common(1)[0][0], "first_page": first_page[no]}
                for no, t in sorted(titles.items(), key=lambda kv: first_page[kv[0]]) if no]
    pages = None
    if BOOK_PDF.exists():
        with _pdf_lock:
            pages = len(pdf_doc())
    return {"retrievers": [{"id": k, "label": v} for k, v in RETRIEVERS.items()],
            "providers": providers, "default_provider": default_provider,
            "defaults": asdict(AgentConfig()), "presets": {k: asdict(v) for k, v in CONFIGS.items()},
            "limits": LIMITS, "filter_keys": ["chapter_no"], "chapters": chapters,
            "pdf": {"available": BOOK_PDF.exists(), "pages": pages, "name": BOOK_PDF.name},
            "streaming": False}


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    provider: str | None = None
    model: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] | None = None
    query_id: str | None = None


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    cfg = build_config(req.config)
    filters = {k: str(v) for k, v in (req.filters or {}).items() if v not in (None, "")} or None
    try:
        check_filters(filters)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    qid = req.query_id or uuid.uuid4().hex[:12]
    t0 = time.perf_counter()
    with _run_lock:
        try:
            retriever = get_retriever(cfg.retriever)
            llm = get_llm(req.provider, req.model)
        except HTTPException:
            raise
        except Exception as exc:  # setup failure: report it as a failed trace, never a fake answer
            err = f"{type(exc).__name__}: {exc}"[:500]
            trace = {"query_id": qid, "question": req.question, "filter": filters, "config": asdict(cfg),
                     "provider": req.provider or os.getenv("LLM_PROVIDER") or "openrouter", "model": req.model,
                     "status": "error", "error": err, "stage": "setup", "answer": "", "citations": [],
                     "external_refs": [], "validation": {}, "events": [{"event": "error"}], "context_ids": [],
                     "context": "", "context_chars": 0, "n_llm_calls": 0, "n_book_searches": 0, "n_external_calls": 0,
                     "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": None,
                     "latency_s": round(time.perf_counter() - t0, 2)}
            return {"trace": trace, "chunks": {}, "error_kind": classify(err)}
        trace = BookAgent(llm, retriever, cfg).run(req.question, filters=filters, query_id=qid)
    ids = set(trace.get("context_ids", [])) | set(trace.get("citations", []))
    for e in trace.get("events", []):
        ids.update(r["id"] for r in e.get("results", []))
    return {"trace": trace, "chunks": {i: v for i in ids if (v := chunk_view(i))},
            "error_kind": classify(trace.get("error", "")) if trace["status"] == "error" else None}


# --------------------------------------------------------------------------- PDF
@functools.lru_cache(maxsize=1)
def pdf_doc():
    import pymupdf
    if not BOOK_PDF.exists():
        raise HTTPException(404, f"PDF not found at {BOOK_PDF} (set BOOK_PDF)")
    return pymupdf.open(BOOK_PDF)


def _page(n: int):
    doc = pdf_doc()
    if not 1 <= n <= len(doc):
        raise HTTPException(404, f"page {n} out of range 1..{len(doc)}")
    return doc[n - 1]


@app.get("/api/pdf")
def pdf_file():
    if not BOOK_PDF.exists():
        raise HTTPException(404, "PDF not found")
    return FileResponse(BOOK_PDF, media_type="application/pdf", filename=BOOK_PDF.name)


@functools.lru_cache(maxsize=64)
def _png(n: int, scale: float) -> bytes:
    import pymupdf
    with _pdf_lock:
        return _page(n).get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes("png")


@app.get("/api/pdf/page/{n}.png")
def page_png(n: int, scale: float = Query(1.5, ge=0.5, le=3.0)):
    return Response(_png(n, round(scale * 4) / 4), media_type="image/png", headers={"Cache-Control": "max-age=3600"})


@functools.lru_cache(maxsize=32)
def _page_chars(n: int):
    """Non-space characters of the page with their boxes, in the same order as Day 6 ingestion (rawdict)."""
    with _pdf_lock:
        page = _page(n)
        raw = page.get_text("rawdict")
        width, height = page.rect.width, page.rect.height
    entries: list[list[Any]] = []
    for b in raw["blocks"]:
        if b["type"] != 0:
            continue
        for ln in b["lines"]:
            for s in ln["spans"]:
                for ch in s["chars"]:
                    c = ch["c"]
                    if not c or c.isspace() or unicodedata.category(c) == "Cc":
                        continue
                    if unicodedata.combining(c) and entries:  # attach accent to its base letter
                        entries[-1][0] = unicodedata.normalize("NFC", entries[-1][0] + c)
                        continue
                    entries.append([unicodedata.normalize("NFC", c), tuple(ch["bbox"])])
    key, owner = [], []
    for i, (t, _) in enumerate(entries):
        t = t.casefold()
        key.append(t)
        owner.extend([i] * len(t))
    return entries, "".join(key), owner, width, height


def _norm_key(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFC", text).casefold() if not c.isspace() and unicodedata.category(c) != "Cc")


def _rects(entries, idx: list[int]) -> list[list[float]]:
    rects: list[list[float]] = []
    for i in idx:
        x0, y0, x1, y1 = entries[i][1]
        if rects and abs(y0 - rects[-1][1]) < 2.5 and x0 >= rects[-1][0] - 1:
            r = rects[-1]
            r[0], r[1], r[2], r[3] = min(r[0], x0), min(r[1], y0), max(r[2], x1), max(r[3], y1)
        else:
            rects.append([x0, y0, x1, y1])
    return [[round(v, 1) for v in r] for r in rects]


@app.get("/api/pdf/page/{n}/locate")
def locate(n: int, chunk_id: list[str] = Query(default=[])) -> dict[str, Any]:
    entries, key, owner, width, height = _page_chars(n)
    matches = []
    for cid in chunk_id:
        c = CHUNKS.get(cid)
        if c is None:
            matches.append({"chunk_id": cid, "found": False, "reason": "unknown chunk id"}); continue
        if c["page"] != n:
            matches.append({"chunk_id": cid, "found": False, "reason": f"chunk is on page {c['page']}"}); continue
        ck = _norm_key(c["text"])
        start, end, method = key.find(ck), -1, "exact"
        if start >= 0:
            end = start + len(ck)
        else:  # fall back to both ends of the chunk; only accept a tight span
            head, tail = ck[:60], ck[-60:]
            s = key.find(head)
            e = key.find(tail, s + 1) if s >= 0 else -1
            if s >= 0 and e >= 0 and (e + len(tail) - s) <= len(ck) * 1.3:
                start, end, method = s, e + len(tail), "anchors"
        if start < 0 or end < 0:
            matches.append({"chunk_id": cid, "found": False, "reason": "text not matched on the page"}); continue
        idx = sorted(set(owner[start:end]))
        matches.append({"chunk_id": cid, "found": True, "method": method, "rects": _rects(entries, idx)})
    return {"page": n, "width": width, "height": height, "matches": matches}


if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")


def _port_free(host: str, port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def main(argv: list[str] | None = None) -> int:
    """python -m src.api [--port 8800] [--host 127.0.0.1]   (or env PORT / HOST)

    With no explicit port, a busy default port falls back to the next free one (up to +20).
    An explicitly requested port that is busy is an error (no silent switch)."""
    import argparse
    import sys
    import uvicorn
    ap = argparse.ArgumentParser(description="Run the RAG workbench API + UI")
    ap.add_argument("--host", default=os.getenv("HOST") or "127.0.0.1")
    ap.add_argument("--port", type=int, default=None, help="default: env PORT or 8765")
    args = ap.parse_args(argv)
    explicit = args.port is not None or bool(os.getenv("PORT"))
    port = args.port or int(os.getenv("PORT") or 8765)
    if not _port_free(args.host, port):
        if explicit:
            print(f"Port {port} is already in use. Pick another one: python -m src.api --port {port + 1}", file=sys.stderr)
            return 1
        free = next((p for p in range(port + 1, port + 21) if _port_free(args.host, p)), None)
        if free is None:
            print(f"Ports {port}-{port + 20} are all busy; use --port <n>", file=sys.stderr)
            return 1
        print(f"Port {port} is busy -> using {free}")
        port = free
    print(f"RAG Workbench: http://{args.host}:{port}")
    uvicorn.run(app, host=args.host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
