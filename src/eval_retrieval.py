"""Benchmark the retrieval methods on one split with identical questions, index and hit definition.

Metrics (answerable questions only; unanswerable ones are excluded from the denominator, BENCHMARK.md):
  Hit@1, Evidence Hit@3, Hit@10, MRR@10      hit = chunk with gold source_id + page that contains the evidence
  Context Evidence Rate @ budget             top-3 packed with starter `pack_context` (chars, incl. source line)
  median latency (ms), cost (local = 0 USD)

The hit definition and context packing are imported from starter/baseline.py so every method is measured
exactly like the TF-IDF baseline. The question's own `filter` (given by the user) is applied when
--use-filter is on; gold never reaches a retriever.

Run from the repo root:  python -m src.eval_retrieval --split dev [--methods tfidf,bm25,...] [--no-filter]
Writes results/retrieval/<split>/<method>.traces.json, summary.json and summary.md.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from src.retrieval import DAY7, BM25Retriever, DenseRetriever, HybridRetriever, load_chunks

sys.path.insert(0, str(DAY7 / "starter"))
from baseline import TfidfIndex, hit, pack_context  # noqa: E402  (starter is not a package)

QUESTIONS = DAY7 / "data" / "book" / "questions.json"
ALL_METHODS = ["tfidf", "bm25", "bm25_2gram", "dense", "hybrid", "hybrid_2gram"]
BUDGETS = (800, 2400)
EVAL_K = 10


class TfidfRetriever:
    """Adapter so the starter baseline has the same interface (it has no filter support -> filter post-hoc)."""
    name = "tfidf"

    def __init__(self, chunks):
        self.index = TfidfIndex(chunks)

    def search(self, query, *, filters=None, top_k=3):
        from src.retrieval import matches
        rows = [r for r in self.index.search(query, top_k=len(self.index.chunks)) if matches(r, filters)][:top_k]
        return [{**r, "rank": i + 1} for i, r in enumerate(rows)]


def build(methods: list[str], chunks) -> dict:
    dense = DenseRetriever() if any(m.startswith(("dense", "hybrid")) for m in methods) else None
    lex = {1: BM25Retriever(chunks, ngram=1), 2: BM25Retriever(chunks, ngram=2)}
    table = {
        "tfidf": lambda: TfidfRetriever(chunks),
        "bm25": lambda: lex[1],
        "bm25_2gram": lambda: lex[2],
        "dense": lambda: dense,
        "hybrid": lambda: HybridRetriever(dense, lex[1]),
        "hybrid_2gram": lambda: HybridRetriever(dense, lex[2]),
    }
    unknown = set(methods) - set(table)
    if unknown:
        raise ValueError(f"unknown methods {sorted(unknown)}; choose from {ALL_METHODS}")
    return {m: table[m]() for m in methods}


def evaluate(name: str, retriever, questions: list[dict], use_filter: bool) -> tuple[list[dict], dict]:
    traces = []
    for q in questions:
        flt = q.get("filter") if use_filter else None
        t0 = time.perf_counter()
        results = retriever.search(q["question"], filters=flt, top_k=EVAL_K)
        ms = (time.perf_counter() - t0) * 1000
        marks = [hit(r, q["gold"]) for r in results]
        first = next((i + 1 for i, m in enumerate(marks) if m), None)
        top3 = results[:3]
        ctx = {}
        for budget in BUDGETS:
            _, ids = pack_context(top3, budget=budget)
            ctx[budget] = any(m and r["id"] in ids for r, m in zip(top3, marks))
        traces.append({
            "query_id": q["id"], "question": q["question"], "filter": flt, "method": name, "elapsed_ms": round(ms, 1),
            "first_hit_rank": first, "hit1": first == 1, "hit3": bool(first and first <= 3),
            "hit10": first is not None, **{f"ctx{b}": v for b, v in ctx.items()},
            "results": [{"rank": r["rank"], "id": r["id"], "page": r["page"], "score": round(r["score"], 4),
                         "chapter": r["metadata"].get("chapter"), "hit": m,
                         **({"components": r["components"]} if "components" in r else {}),
                         "text": r["text"] if r["rank"] <= 3 else r["text"][:160]}
                        for r, m in zip(results, marks)],
        })
    n = len(traces)
    summary = {"method": name, "n": n, "use_filter": use_filter,
               "hit1": sum(t["hit1"] for t in traces), "hit3": sum(t["hit3"] for t in traces),
               "hit10": sum(t["hit10"] for t in traces),
               "mrr10": round(sum(1 / t["first_hit_rank"] for t in traces if t["first_hit_rank"]) / n, 3),
               **{f"ctx{b}": sum(t[f"ctx{b}"] for t in traces) for b in BUDGETS},
               "median_ms": round(statistics.median(t["elapsed_ms"] for t in traces), 1),
               "cost_usd": 0.0,
               "misses_at3": [t["query_id"] for t in traces if not t["hit3"]]}
    return traces, summary


def to_markdown(rows: list[dict], split: str) -> str:
    def pct(k, r):
        return f"{r[k]}/{r['n']} ({r[k] / r['n']:.0%})"
    lines = [f"# Retrieval benchmark — split `{split}` (answerable questions only)", "",
             f"| Method | Hit@1 | Evidence Hit@3 | Hit@10 | MRR@10 | Ctx@{BUDGETS[0]} | Ctx@{BUDGETS[1]} | median ms | cost | misses@3 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['method']} | {pct('hit1', r)} | {pct('hit3', r)} | {pct('hit10', r)} | {r['mrr10']} | "
                     f"{pct(f'ctx{BUDGETS[0]}', r)} | {pct(f'ctx{BUDGETS[1]}', r)} | {r['median_ms']} | {r['cost_usd']} | "
                     f"{', '.join(r['misses_at3']) or '-'} |")
    lines += ["", f"Ctx@B = gold evidence present in the top-3 packed into B characters (starter `pack_context`).",
              f"Filter from the question applied: {rows[0]['use_filter']}. Same chunks.json / pgvector index for every method."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", required=True, choices=("dev", "test"))
    ap.add_argument("--methods", default=",".join(ALL_METHODS))
    ap.add_argument("--no-filter", action="store_true", help="ignore the user-given filter in questions")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    questions = [q for q in json.loads(QUESTIONS.read_text(encoding="utf-8")) if q["split"] == args.split]
    chunks = load_chunks()
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    retrievers = build(methods, chunks)
    out = args.out or DAY7 / "results" / "retrieval" / (args.split + ("-nofilter" if args.no_filter else ""))
    out.mkdir(parents=True, exist_ok=True)
    if any(isinstance(r, (DenseRetriever, HybridRetriever)) for r in retrievers.values()):
        next(r for r in retrievers.values() if isinstance(r, (DenseRetriever, HybridRetriever))).search("khởi động", top_k=1)  # warm-up (model load / CUDA)

    summaries = []
    for name, r in retrievers.items():
        traces, summary = evaluate(name, r, questions, use_filter=not args.no_filter)
        (out / f"{name}.traces.json").write_text(json.dumps(traces, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        summaries.append(summary)
        print(f"{name:13s} hit1={summary['hit1']}/{summary['n']} hit3={summary['hit3']} hit10={summary['hit10']} "
              f"mrr={summary['mrr10']} ctx800={summary['ctx800']} ctx2400={summary['ctx2400']} {summary['median_ms']}ms "
              f"misses@3={summary['misses_at3']}")
    (out / "summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "summary.md").write_text(to_markdown(summaries, args.split), encoding="utf-8")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
