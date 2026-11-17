"""Step 2: describe every visual region with a vision LLM (index-time text for retrieval).

    python -m src.advanced.describe [--ids p104|v00,...] [--workers 4] [--provider gemini]

For each crop (original PDF pixels, caption included) the model returns JSON:
  {"type": table|chart|diagram|image|formula|other, "title": ..., "content": ...}
  table   -> full markdown transcription (numbers, units, headers kept)
  chart   -> chart kind, axes (name, unit, range), legend/series, readable values, trends
  diagram -> components, labels, arrows/relations, symbols shown
These descriptions are used ONLY for retrieval. Answers about exact values re-read the crop at query
time (tool inspect_visual), and benchmark gold is written from the original page, never from this text.
Cached in data/advanced/descriptions.json keyed by region id + crop hash; failures are recorded, not hidden.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from src.llm import LLMClient

DAY7 = Path(__file__).resolve().parents[2]
REGIONS = DAY7 / "data" / "advanced" / "regions.json"
CACHE = DAY7 / "data" / "advanced" / "descriptions.json"

PROMPT = """Ảnh là một vùng cắt từ trang {page} của sách "Machine Learning cơ bản" (Vũ Hữu Tiệp).
Chú thích gần vùng này: {caption}

Hãy mô tả CHÍNH XÁC những gì nhìn thấy, bằng tiếng Việt, để người khác tìm kiếm và trả lời câu hỏi về hình này.
- Nếu là BẢNG: chép lại đầy đủ dạng bảng markdown, giữ nguyên tiêu đề cột/hàng, số, đơn vị, ký hiệu.
- Nếu là BIỂU ĐỒ/ĐỒ THỊ: loại biểu đồ; tên, đơn vị và khoảng giá trị của từng trục; chú giải từng đường/màu/ký hiệu; các giá trị đọc được (ghi rõ là xấp xỉ); xu hướng và so sánh chính; tiêu đề các hình con (a), (b)...
- Nếu là SƠ ĐỒ/ẢNH: các thành phần, nhãn, mũi tên/quan hệ, số và ký hiệu xuất hiện.
- Nếu là công thức đóng khung: chép công thức (LaTeX).
Không suy đoán ngoài hình; chỗ nào không đọc được thì ghi "không đọc được".
Trả về DUY NHẤT một JSON: {{"type": "table|chart|diagram|image|formula|other", "title": "...", "content": "..."}}"""

_lock = threading.Lock()


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if m:
        try:
            out = json.loads(m.group(0))
            if isinstance(out, dict) and out.get("content"):
                return {"type": str(out.get("type", "other")), "title": str(out.get("title", "")), "content": str(out["content"])}
        except json.JSONDecodeError:
            pass
    return {"type": "other", "title": "", "content": (text or "").strip(), "parse_error": True}


def describe(llm: LLMClient, region: dict) -> dict:
    path = DAY7 / region["crop"]
    b64 = base64.b64encode(path.read_bytes()).decode()
    caption = region["caption"] or (f"(không có; hình gần nhất trên trang: {region['related_caption']})" if region["related_caption"] else "(không có)")
    msg = [{"role": "user", "content": [
        {"type": "text", "text": PROMPT.format(page=region["page"], caption=caption)},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}]
    r = llm.chat(msg, max_tokens=2048)
    return {**_parse(r.text), "model": f"{llm.provider}/{llm.model}", "prompt_tokens": r.prompt_tokens,
            "completion_tokens": r.completion_tokens, "cost_usd": r.cost_usd, "latency_s": round(r.latency_s, 2),
            "crop_hash": _hash(path)}


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ids", default="", help="comma-separated short ids like p104|v00 (default: all)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--provider", default="gemini")
    ap.add_argument("--model", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    regions = [r for r in json.loads(REGIONS.read_text(encoding="utf-8"))["regions"] if not r["skip_vision"]]
    if args.ids:
        want = set(args.ids.split(","))
        regions = [r for r in regions if r["id"].split("|", 1)[1] in want]
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    todo = [r for r in regions if args.force or r["id"] not in cache or cache[r["id"]].get("error")
            or cache[r["id"]].get("crop_hash") != _hash(DAY7 / r["crop"])]
    print(f"{len(regions)} regions, {len(todo)} to describe")
    llm = LLMClient(args.provider, args.model)
    t0 = time.perf_counter()
    done = 0

    def save():
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(describe, llm, r): r for r in todo}
        for f in as_completed(futs):
            r = futs[f]
            try:
                res = f.result()
            except Exception as exc:  # recorded, retried on the next run
                res = {"error": f"{type(exc).__name__}: {exc}"[:300]}
            with _lock:
                cache[r["id"]] = res
                done += 1
                if done % 10 == 0:
                    save()
            print(f"[{done}/{len(todo)}] {r['id'].split('|', 1)[1]} {res.get('type', 'ERR')} {res.get('error', '')[:80]}")
    save()
    ok = [v for v in cache.values() if not v.get("error")]
    print(f"done in {time.perf_counter() - t0:.0f}s | cached ok={len(ok)} errors={sum(bool(v.get('error')) for v in cache.values())} "
          f"| tokens in={sum(v.get('prompt_tokens', 0) for v in ok)} out={sum(v.get('completion_tokens', 0) for v in ok)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
