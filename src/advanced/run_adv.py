"""Run the multimodal agent on the advanced benchmark and score it.

    python -m src.advanced.run_adv run   --split dev  --config mm_hybrid [--ids ad01,ad02] [--fresh]
    python -m src.advanced.run_adv score --split test --config mm_hybrid      # after labels are filled

`run` (resumable, one trace saved per case) writes results/advanced/<split>/<config>/:
  traces.json        full trace per case: tool calls + params, search results, inspect_visual reads,
                     final context, answer, citations, latency, tokens, cost, errors
  auto.json/.md      automatic proxies per group (NOT the pass/fail score):
                     context_has_gold = final context holds a chunk/region on an evidence page
                     (visual evidence: region with that caption, or a text chunk of that page),
                     cites_gold = a citation points to such a chunk/region; abstain status per group
  labels_todo.json   one row per case for the human pass/fail decision (ADVANCED.md section 3)
`score` reads labels.json (same rows with "pass": true/false and "reason") and reports n/N overall and by group,
with system errors counted as fails and listed separately.
Only the question goes to the agent; gold is read after the run, for scoring.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

DAY7 = Path(__file__).resolve().parents[2]
BENCH = DAY7 / "data" / "advanced" / "benchmark_adv.json"
GROUPS = ["table", "image", "chart", "multihop", "text", "unanswerable"]


def out_dir(split: str, config: str, provider: str, tag: str = "") -> Path:
    """`tag` keeps repeat runs (e.g. rerun2) apart from the official run, which is never overwritten."""
    return DAY7 / "results" / "advanced" / split / (f"{config}__{provider}" + (f"__{tag}" if tag else ""))


def gold_hits(case: dict, ids: list[str], regions: dict, chunks: dict) -> bool:
    for ev in case.get("evidence", []):
        for i in ids:
            if i in regions and regions[i]["page"] == ev["page"] and ev["kind"] != "text":
                labels = (regions[i]["caption_label"] or regions[i]["related_caption"]).split("; ")
                if ev["ref"] in labels:
                    return True
            elif i in chunks and chunks[i]["page"] == ev["page"]:
                if ev["kind"] == "text" and ev["detail"] in chunks[i]["text"]:
                    return True
                if ev["kind"] != "text" and ev["ref"] in chunks[i]["text"]:
                    return True  # table transcribed in the text layer (LaTeX tables are text)
    return False


def auto_metrics(traces: list[dict], cases: dict, regions: dict, chunks: dict) -> dict:
    per = defaultdict(lambda: Counter())
    for t in traces:
        c = cases[t["query_id"]]
        g = c["group"]
        per[g]["N"] += 1
        per[g]["error"] += t["status"] == "error"
        per[g]["abstain"] += t["status"] == "abstain"
        if c["answerable"]:
            per[g]["context_has_gold"] += gold_hits(c, t["context_ids"], regions, chunks)
            per[g]["cites_gold"] += t["status"] == "answered" and gold_hits(c, t["citations"], regions, chunks)
        per[g]["inspect_calls"] += sum(e["event"] == "inspect_visual" for e in t["events"])
    ran = [t for t in traces if t["status"] != "error"]
    costs = [t["cost_usd"] for t in ran]
    insp_tokens = sum(e.get("prompt_tokens", 0) + e.get("completion_tokens", 0) for t in ran for e in t["events"] if e["event"] == "inspect_visual")
    return {"by_group": {g: dict(per[g]) for g in GROUPS if g in per},
            "cases": len(traces), "errors": [t["query_id"] for t in traces if t["status"] == "error"],
            "latency_s": {"median": round(statistics.median(t["latency_s"] for t in traces), 1), "max": max(t["latency_s"] for t in traces)} if traces else None,
            "llm_tokens": {"prompt": sum(t["prompt_tokens"] for t in ran), "completion": sum(t["completion_tokens"] for t in ran)},
            "inspect_visual_tokens": insp_tokens,
            "cost_usd": None if not costs or any(c is None for c in costs) else round(sum(costs), 5)}


def run(args) -> int:
    from src.advanced.mm_agent import MM_CONFIGS, make_mm_agent
    cases = {c["id"]: c for c in json.loads(BENCH.read_text(encoding="utf-8")) if c["split"] == args.split}
    todo = [cid for cid in cases if not args.ids or cid in args.ids.split(",")]
    agent = make_mm_agent(args.config, args.provider, args.model)
    out = out_dir(args.split, args.config, agent.llm.provider, args.tag)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "traces.json"
    done = {} if args.fresh or not path.exists() else {t["query_id"]: t for t in json.loads(path.read_text(encoding="utf-8"))}
    for cid in todo:
        if cid in done and done[cid]["status"] != "error":
            continue
        t = agent.run(cases[cid]["question"], query_id=cid)  # question only: no gold, no group label
        t["group"] = cases[cid]["group"]
        done[cid] = t
        path.write_text(json.dumps([done[k] for k in cases if k in done], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        insp = sum(e["event"] == "inspect_visual" for e in t["events"])
        print(f"{cid} {t['group']:12s} [{t['status']:8s}] search={t['n_book_searches']} inspect={insp} {t['latency_s']:5.1f}s "
              f"cites={[c.split('|', 1)[1] for c in t['citations']]} {('ERR ' + t['error'][:90]) if t.get('error') else ''}")
    traces = [done[k] for k in cases if k in done]
    regions = {r["id"]: r for r in json.loads((DAY7 / "data" / "advanced" / "regions.json").read_text(encoding="utf-8"))["regions"]}
    chunks = {c["id"]: c for c in json.loads((DAY7 / "data" / "book" / "chunks.json").read_text(encoding="utf-8"))}
    am = {"split": args.split, "config": MM_CONFIGS[args.config].__dict__, "provider": agent.llm.provider, "model": agent.llm.model,
          **auto_metrics(traces, cases, regions, chunks)}
    (out / "auto.json").write_text(json.dumps(am, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = ["| Group | N | context has gold | cites gold | abstain | errors | inspect calls |", "|---|---|---|---|---|---|---|"]
    for g, m in am["by_group"].items():
        rows.append(f"| {g} | {m.get('N', 0)} | {m.get('context_has_gold', '-') if g != 'unanswerable' else '-'} | "
                    f"{m.get('cites_gold', '-') if g != 'unanswerable' else '-'} | {m.get('abstain', 0)} | {m.get('error', 0)} | {m.get('inspect_calls', 0)} |")
    (out / "auto.md").write_text(f"# Auto proxies — {args.split} / {args.config} / {agent.llm.provider}/{agent.llm.model}\n\n" + "\n".join(rows) +
                                 f"\n\nLatency {am['latency_s']}, LLM tokens {am['llm_tokens']}, inspect_visual tokens {am['inspect_visual_tokens']}, "
                                 f"cost {am['cost_usd']}. Errors: {am['errors'] or 'none'}.\nPass/fail is decided by reading each answer against the original page (labels.json).\n", encoding="utf-8")
    labels = [{"id": t["query_id"], "group": t["group"], "status": t["status"], "question": t["question"],
               "expected": cases[t["query_id"]].get("expected_answer") or "abstain", "answer": t["answer"],
               "citations": t["citations"], "pass": None, "reason": ""} for t in traces]
    (out / "labels_todo.json").write_text(json.dumps(labels, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(open(out / "auto.md", encoding="utf-8").read())
    return 0


def score(args) -> int:
    out = out_dir(args.split, args.config, args.provider, args.tag)
    labels = json.loads((out / "labels.json").read_text(encoding="utf-8"))
    traces = {t["query_id"]: t for t in json.loads((out / "traces.json").read_text(encoding="utf-8"))}
    cases = [c for c in json.loads(BENCH.read_text(encoding="utf-8")) if c["split"] == args.split]
    lab = {l["id"]: l for l in labels}
    missing = [c["id"] for c in cases if c["id"] not in lab or not isinstance(lab[c["id"]].get("pass"), bool)]
    if missing:
        print("missing pass/fail labels:", missing)
        return 1
    per = defaultdict(lambda: [0, 0])
    for c in cases:  # every published test case counts; errors are fails (ADVANCED.md)
        ok = lab[c["id"]]["pass"] and traces.get(c["id"], {}).get("status") != "error"
        per[c["group"]][0] += ok
        per[c["group"]][1] += 1
    n, N = sum(v[0] for v in per.values()), sum(v[1] for v in per.values())
    res = {"split": args.split, "config": args.config, "pass": n, "total": N, "rate": round(100 * n / N, 2),
           "meets_90": n * 10 >= 9 * N, "by_group": {g: {"pass": per[g][0], "total": per[g][1]} for g in GROUPS if g in per},
           "system_errors": [k for k, t in traces.items() if t["status"] == "error"],
           "failed": [l["id"] for l in labels if not l["pass"]]}
    (out / "score.json").write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("run", "score"))
    ap.add_argument("--split", required=True, choices=("dev", "test"))
    ap.add_argument("--config", default="mm_hybrid")
    ap.add_argument("--provider", default="gemini")
    ap.add_argument("--model", default=None)
    ap.add_argument("--ids", default="")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--tag", default="", help="separate output folder for repeat runs, e.g. rerun2")
    args = ap.parse_args(argv)
    return run(args) if args.cmd == "run" else score(args)


if __name__ == "__main__":
    sys.exit(main())
