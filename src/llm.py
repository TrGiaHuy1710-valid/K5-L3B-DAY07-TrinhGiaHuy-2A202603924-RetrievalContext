"""Multi-provider chat client with tool calling (OpenAI-compatible API for every provider).

    LLM_PROVIDER = openrouter (default) | gemini | openai | ollama
    LLM_MODEL    = optional override of the provider's default model

| provider   | endpoint                                                   | key env             | default model          |
|------------|------------------------------------------------------------|---------------------|------------------------|
| openrouter | https://openrouter.ai/api/v1                               | OPENROUTER_API_KEY  | openai/gpt-4o-mini     |
| gemini     | https://generativelanguage.googleapis.com/v1beta/openai/   | GEMINI_API_KEY      | gemini-3.5-flash-lite  |
| openai     | (SDK default)                                              | OPENAI_API_KEY      | gpt-4o-mini            |
| ollama     | http://localhost:11434/v1                                  | (none)              | qwen2.5:7b             |

Gemini is reached through Google's OpenAI-compatible endpoint, so one code path (the `openai` SDK,
already installed in env `robot`) serves every provider; no `google-genai` dependency.

Keys are read from the Day 7 `.env` (overrides system env vars), then (fallback, never overriding) from the Day 6 `starter/.env`.
Errors are raised after a few retries; there is NO mock fallback (benchmark must use a real model).

CLI smoke test (costs a few tokens):  python -m src.llm --check [--provider gemini] [--model ...]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DAY7 = Path(__file__).resolve().parent.parent

PROVIDERS: dict[str, dict[str, Any]] = {
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "key_env": "OPENROUTER_API_KEY", "model": "openai/gpt-4o-mini"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "key_env": "GEMINI_API_KEY", "model": "gemini-3.5-flash-lite"},
    "openai": {"base_url": None, "key_env": "OPENAI_API_KEY", "model": "gpt-4o-mini"},
    "ollama": {"base_url": "http://localhost:11434/v1", "key_env": None, "model": "qwen2.5:7b"},
}

# USD per 1M tokens (input, output), list prices used only when the provider does not report cost.
# Estimates: check the provider's pricing page; override with LLM_PRICE_IN / LLM_PRICE_OUT.
PRICES: dict[str, tuple[float, float]] = {
    "openai/gpt-4o-mini": (0.15, 0.60), "gpt-4o-mini": (0.15, 0.60),
    "qwen2.5:7b": (0.0, 0.0),
    # gemini-3.5-flash-lite: no price filled in (not verified) -> cost "unknown" unless LLM_PRICE_IN/OUT are set
}


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    # The project .env wins over stale system-wide variables (e.g. an old GEMINI_API_KEY set in Windows).
    load_dotenv(DAY7 / ".env", override=True)
    from src.day6_bridge import DAY6_STARTER
    load_dotenv(DAY6_STARTER / ".env", override=False)


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]
    raw_args: str = ""


@dataclass
class ChatResult:
    text: str | None
    tool_calls: list[ToolCall]
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float | None = None
    cost_source: str = "unknown"  # "provider" (reported) | "price_table" (estimate) | "unknown"
    latency_s: float = 0.0
    finish_reason: str | None = None
    raw: Any = field(default=None, repr=False)

    def assistant_message(self) -> dict[str, Any]:
        """The assistant turn in OpenAI format, to append to the history before tool results.

        Uses the provider's raw message when available so provider-specific fields survive
        (Gemini 3 needs `extra_content.google.thought_signature` echoed back on tool calls)."""
        if self.raw is not None and self.tool_calls:
            raw_msg = self.raw.choices[0].message.model_dump(exclude_none=True)
            return {"role": "assistant", "content": raw_msg.get("content") or "", "tool_calls": raw_msg["tool_calls"]}
        msg: dict[str, Any] = {"role": "assistant", "content": self.text or ""}
        if self.tool_calls:
            msg["tool_calls"] = [{"id": c.id, "type": "function",
                                  "function": {"name": c.name, "arguments": c.raw_args or json.dumps(c.args, ensure_ascii=False)}}
                                 for c in self.tool_calls]
        return msg


class LLMClient:
    def __init__(self, provider: str | None = None, model: str | None = None, max_retries: int = 4) -> None:
        load_env()
        self.provider = (provider or os.getenv("LLM_PROVIDER") or "openrouter").lower()
        if self.provider not in PROVIDERS:
            raise ValueError(f"unknown provider {self.provider!r}; choose one of {sorted(PROVIDERS)}")
        cfg = PROVIDERS[self.provider]
        self.model = model or os.getenv("LLM_MODEL") or cfg["model"]
        key = os.getenv(cfg["key_env"]) if cfg["key_env"] else "ollama"
        if not key:
            raise RuntimeError(f"{cfg['key_env']} is empty: put it in {DAY7 / '.env'} (see .env.example)")
        import httpx
        from openai import OpenAI
        base_url = os.getenv(f"{self.provider.upper()}_BASE_URL") or cfg["base_url"]
        # connect (TCP + TLS handshake) capped at 10 s: on this network the TLS handshake to openrouter.ai
        # sometimes hangs ~23 s; failing fast and retrying here beats the SDK's 60 s x 2 internal retries.
        self.client = OpenAI(api_key=key, base_url=base_url, timeout=httpx.Timeout(90, connect=10), max_retries=0)
        self.max_retries = max_retries

    def _cost(self, usage: Any, pt: int, ct: int) -> tuple[float | None, str]:
        reported = getattr(usage, "cost", None)
        if reported is None and getattr(usage, "model_extra", None):
            reported = usage.model_extra.get("cost")
        if reported is not None:
            return float(reported), "provider"
        price_in, price_out = os.getenv("LLM_PRICE_IN"), os.getenv("LLM_PRICE_OUT")
        prices = (float(price_in), float(price_out)) if price_in and price_out else PRICES.get(self.model)
        if prices is None:
            return None, "unknown"
        return (pt * prices[0] + ct * prices[1]) / 1e6, "price_table"

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, *,
             tool_choice: Any | None = None, temperature: float = 0.0, max_tokens: int | None = None) -> ChatResult:
        from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature}
        if tools:
            kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if self.provider == "openrouter":
            kwargs["extra_body"] = {"usage": {"include": True}}  # ask OpenRouter to report the real cost
        t0 = time.perf_counter()
        self.last_retries = 0
        for attempt in range(self.max_retries):
            try:
                resp = self.client.chat.completions.create(**kwargs)
                break
            except (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError):
                if attempt == self.max_retries - 1:
                    raise
                self.last_retries += 1
                time.sleep(1 + attempt)
        latency = time.perf_counter() - t0
        if not resp.choices:
            raise RuntimeError(f"{self.provider}: empty response (no choices)")
        choice = resp.choices[0]
        msg = choice.message
        calls = []
        for i, c in enumerate(msg.tool_calls or []):
            raw = c.function.arguments or "{}"
            try:
                args = json.loads(raw)
                if not isinstance(args, dict):
                    raise ValueError
            except (json.JSONDecodeError, ValueError):
                args = {"_invalid_json_arguments": raw}  # surfaced to the agent loop as a tool error
            calls.append(ToolCall(c.id or f"call_{i}", c.function.name, args, raw))
        usage = resp.usage
        pt = getattr(usage, "prompt_tokens", 0) or 0
        ct = getattr(usage, "completion_tokens", 0) or 0
        cost, source = self._cost(usage, pt, ct)
        return ChatResult(msg.content, calls, self.provider, self.model, pt, ct, cost, source, latency,
                          choice.finish_reason, resp)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Smoke-test an LLM provider (plain answer + one tool call).")
    ap.add_argument("--provider", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--check", action="store_true", help="also verify that the model emits a tool call")
    args = ap.parse_args(argv)
    llm = LLMClient(args.provider, args.model)
    r = llm.chat([{"role": "user", "content": "Trả lời đúng một từ: thủ đô của Việt Nam?"}], max_tokens=20)
    print(f"[{llm.provider} / {llm.model}] text={r.text!r} tokens={r.prompt_tokens}+{r.completion_tokens} "
          f"cost={r.cost_usd} ({r.cost_source}) {r.latency_s:.2f}s")
    if args.check:
        tool = {"type": "function", "function": {"name": "search_book", "description": "Tìm đoạn văn trong sách ML.",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}
        r = llm.chat([{"role": "user", "content": "Dùng tool để tìm định nghĩa hàm sigmoid trong sách."}], [tool])
        print(f"tool call -> {[(c.name, c.args) for c in r.tool_calls] or 'NONE (model did not call the tool)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
