"""Multimodal agent = the stage-3 BookAgent + a multimodal retriever + one extra tool, inspect_visual.

    python -m src.advanced.mm_agent "câu hỏi" [--config mm_hybrid] [--provider gemini]

inspect_visual(region_id, question): sends the ORIGINAL crop of a figure/table/chart that is already in the
context to a vision model together with a focused question, and returns what the model reads there. This is
how exact cell values, axis readings and diagram details reach the answer: the index-time description is only
used to FIND the region. The observation is logged in the trace (question, answer, tokens, latency).
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from src.agent import SYSTEM_PROMPT, AgentConfig, BookAgent
from src.llm import LLMClient

DAY7 = Path(__file__).resolve().parents[2]

MM_RULES = """

Quy tắc thêm cho hình, bảng, biểu đồ:
7. search_book trả về cả đoạn văn (id dạng ...|pNNN|NN) và vùng hình/bảng/biểu đồ (id dạng ...|pNNN|vNN). Phần mô tả của vùng hình là tự động, có thể sai số.
8. Khi câu hỏi cần giá trị trong ô bảng, số đọc trên biểu đồ (trục, chú giải, đơn vị), hoặc chi tiết trong sơ đồ/ảnh: gọi inspect_visual(region_id, câu hỏi cụ thể) để đọc trực tiếp ảnh gốc TRƯỚC khi trả lời. Nếu inspect_visual và mô tả mâu thuẫn, tin inspect_visual.
9. Câu hỏi cần kết hợp nhiều nơi (nhiều trang/bảng/hình): tìm nhiều lần, mỗi lần một ý, rồi tổng hợp.
10. Có phép tính: ghi rõ các số lấy từ đâu và từng bước tính, kèm đơn vị. Đọc giá trị xấp xỉ trên biểu đồ thì nói rõ là xấp xỉ.
11. Trích dẫn id của đoạn văn hoặc vùng hình chứa bằng chứng (ghi [id] sau ý tương ứng). Nếu tài liệu không có thông tin được hỏi (ví dụ số liệu, tên, năm không xuất hiện), gọi final_answer với status="abstain"; không đoán."""

# v2 (dev error ad06): the model appended an alternative ("hoặc ...") that no source states
RULE_V2 = """
12. Không thêm phương án thay thế, suy đoán hay chi tiết không có trong nguồn đã trích dẫn (không viết "hoặc ..." nếu nguồn không nói). Nếu hai nguồn khác nhau, nêu rõ từng nguồn nói gì."""

# v3 (test-v1 failure classes, fixed and validated on DEV only): wrong target of the question (at02),
# reading the wrong curve (at16), estimating instead of computing (at18), extra claims when abstaining (at30)
RULE_V3 = """
13. Trước khi trả lời, xác định chính xác đối tượng và điều kiện câu hỏi hỏi (ví dụ "người cao nhất" khác "người nặng nhất"; "đường kiểm tra" khác "đường xác thực") và chỉ dùng đúng hàng/cột/đường đó.
14. Với biểu đồ nhiều đường: xác định đường cần đọc theo chú giải (kiểu nét/ký hiệu) rồi mới đọc giá trị; khi gọi inspect_visual hãy nêu rõ tên đường theo chú giải.
15. Mọi phép tính (cộng, trừ, trung bình, tỉ lệ, sigmoid, ...) phải dùng tool calculate; ghi biểu thức và kết quả.
16. Khi từ chối vì thiếu bằng chứng: chỉ nói phần không có trong tài liệu; không thêm khẳng định khác về nội dung sách."""

CALC_SCHEMA = {"type": "function", "function": {
    "name": "calculate",
    "description": "Tính chính xác một biểu thức số học. Hỗ trợ + - * / ** ( ), các hàm exp, log, sqrt, abs, round, min, max, sigmoid.",
    "parameters": {"type": "object", "properties": {"expression": {"type": "string", "description": "ví dụ: 1/(1+exp(-(1.54*4.25-4.06)))"}},
                   "required": ["expression"]}}}


def safe_eval(expr: str) -> float:
    """Arithmetic only (AST whitelist): no names except the listed math functions, no attributes, no calls to anything else."""
    import ast
    import math
    funcs = {"exp": math.exp, "log": math.log, "sqrt": math.sqrt, "abs": abs, "round": round, "min": min, "max": max,
             "sigmoid": lambda x: 1 / (1 + math.exp(-x))}
    ops = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
           ast.Pow: lambda a, b: a ** b, ast.USub: lambda a: -a, ast.UAdd: lambda a: a}

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in ops:
            right = ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(right) > 100:
                raise ValueError("exponent too large")
            return ops[type(n.op)](ev(n.left), right)
        if isinstance(n, ast.UnaryOp) and type(n.op) in ops:
            return ops[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in funcs and not n.keywords:
            return funcs[n.func.id](*[ev(a) for a in n.args])
        raise ValueError(f"unsupported expression element: {type(n).__name__}")

    if len(expr) > 300:
        raise ValueError("expression too long")
    return float(ev(ast.parse(expr.replace("×", "*").replace("−", "-"), mode="eval")))


def calc_handler(args: dict[str, Any], ctx) -> tuple[str, dict]:
    expr = str(args.get("expression") or "")
    try:
        val = safe_eval(expr)
        return f"{expr} = {val:.6g}", {"event": "calculate", "tool": "calculate", "expression": expr, "result": val}
    except Exception as exc:
        return f"Lỗi tính toán: {exc}", {"event": "calculate", "tool": "calculate", "expression": expr, "error": str(exc)[:200]}


INSPECT_SCHEMA = {"type": "function", "function": {
    "name": "inspect_visual",
    "description": "Xem trực tiếp ảnh gốc của một vùng hình/bảng/biểu đồ (id dạng ...|pNNN|vNN) đã có trong context để đọc chính xác giá trị, nhãn, chi tiết.",
    "parameters": {"type": "object", "properties": {
        "region_id": {"type": "string", "description": "id vùng hình đã có trong context, ví dụ book-ml-co-ban|p104|v00"},
        "question": {"type": "string", "description": "Điều cần đọc trên hình, cụ thể (ô nào, đường nào, giá trị nào)"}},
        "required": ["region_id", "question"]}}}

VISION_PROMPT = """Ảnh là vùng cắt từ trang {page} của sách "Machine Learning cơ bản". Chú thích: {caption}
Hãy trả lời câu hỏi dựa DUY NHẤT vào những gì nhìn thấy trong ảnh. Đọc kỹ trục, đơn vị, chú giải, tiêu đề cột/hàng.
Nếu giá trị chỉ đọc được xấp xỉ, ghi "xấp xỉ". Nếu ảnh không chứa thông tin cần thiết, nói rõ "không thấy trong ảnh".
Câu hỏi: {question}"""

MM_CONFIGS = {
    "mm_hybrid": AgentConfig(name="mm_hybrid", retriever="mm_hybrid", top_k=6, budget_chars=7000, max_new_per_search=4,
                             max_book_searches=5, max_steps=10, external_tools=False),
    # ablations for dev
    "mm_hybrid_noinspect": AgentConfig(name="mm_hybrid_noinspect", retriever="mm_hybrid", top_k=6, budget_chars=7000,
                                       max_new_per_search=4, max_book_searches=5, max_steps=10, external_tools=False),
    # v2 after dev error analysis: more new chunks per search (ad12: the figure was rank 5 and got skipped),
    # larger budget to hold them, + RULE_V2; index v2 adds the chapter to visual chunks
    "mm_hybrid_v2": AgentConfig(name="mm_hybrid_v2", retriever="mm_hybrid", top_k=6, budget_chars=9000, max_new_per_search=6,
                                max_book_searches=5, max_steps=10, external_tools=False),
    # v3 = v2 + calculate tool + RULE_V3 (+ text final_answer recovery in the shared agent loop)
    "mm_hybrid_v3": AgentConfig(name="mm_hybrid_v3", retriever="mm_hybrid", top_k=6, budget_chars=9000, max_new_per_search=6,
                                max_book_searches=5, max_steps=12, external_tools=False),
    "text_hybrid": AgentConfig(name="text_hybrid", retriever="text_hybrid", top_k=5, budget_chars=4000, max_new_per_search=3,
                               max_book_searches=5, max_steps=10, external_tools=False),
}


def make_inspect_tool(vision: LLMClient, regions: dict[str, dict]):
    def handler(args: dict[str, Any], ctx) -> tuple[str, dict]:
        rid = str(args.get("region_id") or "").strip()
        question = str(args.get("question") or "").strip()
        ev = {"event": "inspect_visual", "tool": "inspect_visual", "region_id": rid, "question": question}
        if rid not in regions:
            return f"Lỗi: {rid!r} không phải id vùng hình hợp lệ.", {**ev, "error": "unknown_region"}
        if rid not in ctx.chunks:
            return "Lỗi: chỉ xem được vùng hình đã có trong context (hãy search_book trước).", {**ev, "error": "not_in_context"}
        r = regions[rid]
        b64 = base64.b64encode((DAY7 / r["crop"]).read_bytes()).decode()
        t0 = time.perf_counter()
        res = vision.chat([{"role": "user", "content": [
            {"type": "text", "text": VISION_PROMPT.format(page=r["page"], caption=r["caption"] or r["related_caption"] or "(không có)", question=question or "Mô tả chi tiết.")},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}], max_tokens=1200)
        answer = (res.text or "").strip()
        ev.update({"answer": answer, "page": r["page"], "crop": r["crop"], "model": f"{vision.provider}/{vision.model}",
                   "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens, "cost_usd": res.cost_usd,
                   "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1)})
        return f"inspect_visual {rid} (trang {r['page']}), DỮ LIỆU đọc từ ảnh gốc:\n{answer}", ev
    return handler


def make_mm_agent(config: AgentConfig | str = "mm_hybrid", provider: str | None = "gemini", model: str | None = None,
                  vision_provider: str = "gemini", vision_model: str | None = None) -> BookAgent:
    from src.advanced.mm_retrieval import make_mm_retriever
    cfg = MM_CONFIGS[config] if isinstance(config, str) else config
    regions = {r["id"]: r for r in json.loads((DAY7 / "data" / "advanced" / "regions.json").read_text(encoding="utf-8"))["regions"]}
    extra = {}
    if cfg.name != "mm_hybrid_noinspect" and cfg.retriever != "text_hybrid":
        extra["inspect_visual"] = (INSPECT_SCHEMA, make_inspect_tool(LLMClient(vision_provider, vision_model), regions))
    v3 = cfg.name.endswith("_v3")
    if v3:
        extra["calculate"] = (CALC_SCHEMA, calc_handler)
    prompt = SYSTEM_PROMPT + (MM_RULES if extra else "") + (RULE_V2 if cfg.name.endswith(("_v2", "_v3")) else "") + (RULE_V3 if v3 else "")
    return BookAgent(LLMClient(provider, model), make_mm_retriever(cfg.retriever), replace(cfg), system_prompt=prompt, extra_tools=extra)


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--config", default="mm_hybrid", choices=sorted(MM_CONFIGS))
    ap.add_argument("--provider", default="gemini")
    ap.add_argument("--model", default=None)
    args = ap.parse_args(argv)
    t = make_mm_agent(args.config, args.provider, args.model).run(args.question)
    for e in t["events"]:
        if e["event"] == "search":
            print(f"  · search_book({e['query']!r}) -> added {e['added']}")
        elif e["event"] == "inspect_visual":
            print(f"  · inspect_visual({e['region_id']}, {e['question']!r}) -> {str(e.get('answer', e.get('error')))[:160]!r}")
    print(f"\n[{t['status']}] {t['answer']}\ncitations={t['citations']} llm={t['n_llm_calls']} {t['latency_s']}s "
          f"tokens={t['prompt_tokens']}+{t['completion_tokens']} {t.get('error', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
