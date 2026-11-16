"""Three retrieval methods over the ML textbook, all with the same interface and output.

    retriever.search(query, *, filters=None, top_k=3) -> list[result]
    result = {id, text, source_id, source, page, metadata, score, rank, strategy, (components)}

  DenseRetriever   e5 query embedding ("query: " prefix) -> exact cosine search in pgvector `book_chunks`
                   (the Day 6 index; documents were embedded with "passage: "). Filters run in SQL.
  BM25Retriever    Okapi BM25 in memory over chunks.json. Vietnamese is written in syllables separated by
                   spaces and words are often 2 syllables ("hồi quy", "mất mát"), so `ngram=2` adds
                   syllable bigrams as an approximation of word segmentation (no extra library needed).
  HybridRetriever  Reciprocal Rank Fusion of dense + BM25: score = Σ w / (k + rank). Uses ranks only, so the
                   cosine and BM25 score scales never need to be normalised.

Filters are only those the user gives (e.g. {"chapter_no": "9"}); they never come from gold labels.
"""
from __future__ import annotations

import json
import math
import re
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DAY7 = Path(__file__).resolve().parent.parent
CHUNKS = DAY7 / "data" / "book" / "chunks.json"
FILTER_KEYS = {"page", "part", "chapter_no", "chapter", "section"}


def load_chunks(path: Path = CHUNKS) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_filters(filters: dict[str, Any] | None) -> None:
    bad = set(filters or {}) - FILTER_KEYS
    if bad:
        raise ValueError(f"filter keys {sorted(bad)} not allowed; use {sorted(FILTER_KEYS)}")


def matches(chunk: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    return all((chunk["page"] if k == "page" else chunk["metadata"].get(k)) == v for k, v in (filters or {}).items())


def _ranked(rows: list[tuple[float, dict[str, Any]]], top_k: int, strategy: str) -> list[dict[str, Any]]:
    rows.sort(key=lambda r: (-r[0], r[1]["id"]))
    return [{**c, "score": float(s), "rank": i + 1, "strategy": strategy} for i, (s, c) in enumerate(rows[:top_k])]


# --------------------------------------------------------------------------- #
# 1. Dense (Day 6 vector store)
# --------------------------------------------------------------------------- #
class DenseRetriever:
    name = "dense"

    def __init__(self, embedder=None, store=None) -> None:
        if embedder is None or store is None:
            from src.day6_bridge import connect
            embedder, store = connect()
        self.embedder, self.store = embedder, store
        self.last_embed_ms = 0.0

    def search(self, query: str, *, filters: dict[str, Any] | None = None, top_k: int = 3) -> list[dict[str, Any]]:
        check_filters(filters)
        t0 = time.perf_counter()
        vec = self.embedder.embed_query(query)  # adds the "query: " prefix required by e5
        self.last_embed_ms = (time.perf_counter() - t0) * 1000
        return [{**r, "strategy": self.name} for r in self.store.search(vec, top_k=top_k, filters=filters)]


# --------------------------------------------------------------------------- #
# 2. Lexical BM25
# --------------------------------------------------------------------------- #
def tokenize(text: str, ngram: int = 1) -> list[str]:
    toks = re.findall(r"\w+", unicodedata.normalize("NFC", text).casefold())
    if ngram >= 2:
        toks = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
    return toks


class BM25Retriever:
    def __init__(self, chunks: list[dict[str, Any]] | None = None, *, ngram: int = 1, k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = chunks if chunks is not None else load_chunks()
        self.ngram, self.k1, self.b = ngram, k1, b
        self.name = "bm25" if ngram == 1 else f"bm25_{ngram}gram"
        tfs = [Counter(tokenize(c["text"], ngram)) for c in self.chunks]
        self.doc_len = [sum(tf.values()) for tf in tfs]
        self.avgdl = sum(self.doc_len) / len(self.doc_len)
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)  # term -> [(doc, tf)]
        for i, tf in enumerate(tfs):
            for term, n in tf.items():
                self.postings[term].append((i, n))
        n_docs = len(self.chunks)
        self.idf = {t: math.log(1 + (n_docs - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.postings.items()}

    def search(self, query: str, *, filters: dict[str, Any] | None = None, top_k: int = 3) -> list[dict[str, Any]]:
        check_filters(filters)
        scores: dict[int, float] = defaultdict(float)
        for term in set(tokenize(query, self.ngram)):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, tf in self.postings[term]:
                norm = self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                scores[i] += idf * tf * (self.k1 + 1) / (tf + norm)
        rows = [(s, self.chunks[i]) for i, s in scores.items() if s > 0 and matches(self.chunks[i], filters)]
        return _ranked(rows, top_k, self.name)


# --------------------------------------------------------------------------- #
# 3. Hybrid (RRF)
# --------------------------------------------------------------------------- #
class HybridRetriever:
    def __init__(self, dense: DenseRetriever, lexical: BM25Retriever, *, k: int = 60, candidates: int = 20,
                 w_dense: float = 1.0, w_lexical: float = 1.0) -> None:
        self.dense, self.lexical = dense, lexical
        self.k, self.candidates, self.w_dense, self.w_lexical = k, candidates, w_dense, w_lexical
        self.name = f"hybrid_rrf({dense.name}+{lexical.name})"

    def search(self, query: str, *, filters: dict[str, Any] | None = None, top_k: int = 3) -> list[dict[str, Any]]:
        n = max(self.candidates, top_k)
        lists = {"dense": (self.dense.search(query, filters=filters, top_k=n), self.w_dense),
                 "lexical": (self.lexical.search(query, filters=filters, top_k=n), self.w_lexical)}
        fused: dict[str, float] = defaultdict(float)
        chunk: dict[str, dict[str, Any]] = {}
        comps: dict[str, dict[str, int]] = defaultdict(dict)
        for src, (results, w) in lists.items():
            for r in results:
                fused[r["id"]] += w / (self.k + r["rank"])
                chunk.setdefault(r["id"], {k: v for k, v in r.items() if k not in ("score", "rank", "strategy")})
                comps[r["id"]][src] = r["rank"]  # keep component ranks for the trace
        rows = [(s, {**chunk[cid], "components": comps[cid]}) for cid, s in fused.items()]
        return _ranked(rows, top_k, self.name)


def make_retriever(name: str, *, chunks=None, dense: DenseRetriever | None = None, **kw):
    """name: dense | bm25 | bm25_2gram | hybrid | hybrid_2gram"""
    if name == "dense":
        return dense or DenseRetriever()
    if name in ("bm25", "bm25_2gram"):
        return BM25Retriever(chunks, ngram=2 if name.endswith("2gram") else 1)
    if name in ("hybrid", "hybrid_2gram"):
        return HybridRetriever(dense or DenseRetriever(), BM25Retriever(chunks, ngram=2 if name.endswith("2gram") else 1), **kw)
    raise ValueError(f"unknown retriever {name!r}")
