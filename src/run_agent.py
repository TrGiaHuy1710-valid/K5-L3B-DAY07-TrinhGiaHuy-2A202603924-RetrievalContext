"""Run the book agent on a benchmark split and save traces + automatic metrics + a human-review template.

    python -m src.run_agent --split dev --config base [--provider gemini] [--model ...] [--limit 3] [--ids d01,d16]

Flow per case (data/book/cases.json): agent.run(question, filter given by the user) -> trace. Gold labels are
loaded ONLY afterwards to score the saved context/citations. Traces are written after every case and an
existing run is resumed (finished ids are skipped; `--fresh` starts over; errors are retried on resume).

Outputs  results/agent/<split>/<config>__<provider>/
  traces.json         full traces (tool calls, params, results, context, answer, citations, errors, time, tokens, cost)
  summary.json/.md    automatic metrics (below)
  reviews_todo.json   one entry per case for HUMAN labels (answer_grade 0-2, citation_support, abstention_correct)
                      -> after grading, save as reviews.json and run starter/agent_metrics.py

Automatic metrics (no LLM judge; grounding still has to be read by a human, BENCHMARK.md section 3):
  tool_use                 cases with >= 1 search_book call / cases that ran
  context_evidence_rate    answerable cases whose FINAL context holds a gold-evidence chunk / answerable cases
  cited_gold (proxy)       answerable answered cases citing a gold-evidence chunk / answerable cases
  abstention / false_abstention, answer_with_citation, invalid citations dropped, steps, latency, tokens, cost
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

from src.agent import make_agent
from src.agent_configs import CONFIGS
from src.retrieval import DAY7, load_chunks

sys.path.insert(0, str(DAY7 / "starter"))
from baseline import hit  # noqa: E402  same hit definition as the retrieval benchmark

BOOK = DAY7 / "data" / "book"


def score(traces: list[dict], cases: dict, gold: dict, chunks: dict) -> dict:
    ran = [t for t in traces if t["status"] != "error"]
    ans = [t for t in ran if cases[t["query_id"]]["answerable"]]
    una = [t for t in ran if not cases[t["query_id"]]["answerable"]]

    def has_gold(ids, qid):
        return any(hit(chunks[i], gold[qid]) for i in ids if i in chunks)

    for t in ran:  # per-trace automatic labels (kept in the trace file for reading)
        if cases[t["query_id"]]["answerable"]:
            t["auto"] = {"context_has_gold": has_gold(t["context_ids"], t["query_id"]),
                         "cites_gold": has_gold(t["citations"], t["query_id"])}
    n_ans, n_una = len(ans), len(una)
    lat = [t["latency_s"] for t in ran]
    costs = [t["cost_usd"] for t in ran]
    return {
        "cases": len(traces), "ran": len(ran), "provider_errors": len(traces) - len(ran),
        "errors": {t["query_id"]: t.get("error") for t in traces if t["status"] == "error"},
        "status": dict(Counter(t["status"] for t in traces)),
        "tool_use": {"n": sum(t["n_book_searches"] > 0 for t in ran), "N": len(ran)},
        "book_searches_distribution": dict(sorted(Counter(t["n_book_searches"] for t in ran).items())),
        "llm_calls_distribution": dict(sorted(Counter(t["n_llm_calls"] for t in ran).items())),
        "context_evidence_rate": {"n": sum(t["auto"]["context_has_gold"] for t in ans), "N": n_ans},
        "cited_gold_proxy": {"n": sum(t["status"] == "answered" and t["auto"]["cites_gold"] for t in ans), "N": n_ans},
        "answer_with_citation": {"n": sum(bool(t["citations"]) for t in ran if t["status"] == "answered"),
                                 "N": sum(t["status"] == "answered" for t in ran)},
        "citations_in_answer_text": {"n": sum(t["validation"].get("citations_in_text", False) for t in ran if t["status"] == "answered"),
                                     "N": sum(t["status"] == "answered" for t in ran)},
        "invalid_citations_dropped": sum(len(t["validation"].get("invalid_citations", [])) for t in ran),
        "abstention": {"n": sum(t["status"] == "abstain" for t in una), "N": n_una},
        "false_abstention": {"n": sum(t["status"] == "abstain" for t in ans), "N": n_ans},
        "external_calls": sum(t["n_external_calls"] for t in ran),
        "avg_context_chars": round(statistics.mean(t["context_chars"] for t in ran), 1) if ran else None,
        "latency_s": {"median": round(statistics.median(lat), 2), "max": max(lat)} if lat else None,
        "tokens": {"prompt": sum(t["prompt_tokens"] for t in ran), "completion": sum(t["completion_tokens"] for t in ran)},
        "cost_usd_total": None if not costs or any(c is None for c in costs) else round(sum(costs), 5),
        "misses_context": [t["query_id"] for t in ans if not t["auto"]["context_has_gold"]],
        "false_abstain_ids": [t["query_id"] for t in ans if t["status"] == "abstain"],
        "answered_unanswerable_ids": [t["query_id"] for t in una if t["status"] != "abstain"],
    }


def to_md(s: dict, title: str) -> str:
    def f(k):
        v = s[k]
        return f"{v['n']}/{v['N']}" + (f" ({v['n'] / v['N']:.0%})" if v["N"] else " (n/a)")
    rows = [("Tool use (search_book)", f("tool_use")), ("Context Evidence Rate", f("context_evidence_rate")),
            ("Cites a gold chunk (auto proxy)", f("cited_gold_proxy")), ("Answers with citation", f("answer_with_citation")),
            ("[chunk-id] written in answer", f("citations_in_answer_text")), ("Abstention (unanswerable)", f("abstention")),
            ("False abstention (answerable)", f("false_abstention")), ("Invalid citations dropped", s["invalid_citations_dropped"]),
            ("Book searches / case", s["book_searches_distribution"]), ("LLM calls / case", s["llm_calls_distribution"]),
            ("Avg context chars", s["avg_context_chars"]), ("Latency s (median / max)", s["latency_s"]),
            ("Tokens", s["tokens"]), ("Cost USD", s["cost_usd_total"]), ("Provider errors", s["provider_errors"]),
            ("Context misses", ", ".join(s["misses_context"]) or "-"), ("False abstain", ", ".join(s["false_abstain_ids"]) or "-"),
            ("Answered unanswerable", ", ".join(s["answered_unanswerable_ids"]) or "-")]
    return f"# {title}\n\n| Metric | Value |\n|---|---|\n" + "\n".join(f"| {a} | {b} |" for a, b in rows) + \
        "\n\nAutomatic only. Answer grade and citation support must be read and labelled by a human (reviews.json).\n"


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", required=True, choices=("dev", "test"))
    ap.add_argument("--config", default="base", choices=sorted(CONFIGS))
    ap.add_argument("--provider", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--ids", default="", help="comma-separated case ids")
    ap.add_argument("--fresh", action="store_true", help="ignore an existing traces.json")
    args = ap.parse_args(argv)

    cfg = CONFIGS[args.config]
    agent = make_agent(cfg, args.provider, args.model)
    cases = {c["id"]: c for c in json.loads((BOOK / "cases.json").read_text(encoding="utf-8")) if c["split"] == args.split}
    questions = {q["id"]: q for q in json.loads((BOOK / "questions.json").read_text(encoding="utf-8"))}
    todo = [cid for cid in cases if not args.ids or cid in args.ids.split(",")][: args.limit]

    out = DAY7 / "results" / "agent" / args.split / f"{cfg.name}__{agent.llm.provider}"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "traces.json"
    done = {} if args.fresh or not path.exists() else {t["query_id"]: t for t in json.loads(path.read_text(encoding="utf-8"))}
    for cid in todo:
        if cid in done and done[cid]["status"] != "error":
            continue
        flt = questions.get(cid, {}).get("filter")  # user-given scope only; gold is NOT passed
        t = agent.run(cases[cid]["question"], filters=flt, query_id=cid)
        done[cid] = t
        path.write_text(json.dumps([done[k] for k in cases if k in done], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{cid} [{t['status']:8s}] searches={t['n_book_searches']} llm={t['n_llm_calls']} {t['latency_s']:6.1f}s "
              f"cites={t['citations']} {('ERR ' + t['error'][:80]) if t.get('error') else ''}")

    traces = [done[k] for k in cases if k in done]
    chunks = {c["id"]: c for c in load_chunks()}
    gold = {k: q["gold"] for k, q in questions.items()}
    summary = {"split": args.split, "config": cfg.__dict__, "provider": agent.llm.provider, "model": agent.llm.model,
               **score(traces, cases, gold, chunks)}
    path.write_text(json.dumps(traces, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")  # now with `auto` labels
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "summary.md").write_text(to_md(summary, f"Agent `{cfg.name}` on {args.split} — {agent.llm.provider}/{agent.llm.model}"), encoding="utf-8")
    review = [{"query_id": t["query_id"], "answerable": cases[t["query_id"]]["answerable"], "status": t["status"],
               "question": t["question"], "answer": t["answer"], "citations": t["citations"],
               "answer_grade": None if cases[t["query_id"]]["answerable"] else "n/a",
               "citation_support": [None] * len(t["citations"]),
               "abstention_correct": None if not cases[t["query_id"]]["answerable"] else "n/a", "notes": ""}
              for t in traces if t["status"] != "error"]
    (out / "reviews_todo.json").write_text(json.dumps(review, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("status", "tool_use", "context_evidence_rate", "abstention", "false_abstention",
                                               "latency_s", "cost_usd_total")}, ensure_ascii=False))
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
