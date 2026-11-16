"""arXiv and GitHub search, reused from the Day 3 lab (K5-L3B-DAY03-.../starter_v0/tools).

The Day 3 functions are imported unchanged; this module only
  * puts the Day 3 starter on sys.path (override with env DAY3_STARTER),
  * trims their output to what the model needs (fewer tokens),
  * fixes one default: GitHub `sort=stars` ranks keyword-stuffed spam repos first, so `best_match` is used.
Network/API errors are returned as {"error": ...} (the Day 3 contract) and logged in the trace; never mocked.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

DAY7 = Path(__file__).resolve().parent.parent
DAY3_STARTER = Path(os.getenv("DAY3_STARTER") or DAY7.parent / "K5-L3B-DAY03-Nhom5W-ResearchAgentToolEval" / "starter_v0")  # empty = unset


def _day3():
    if not (DAY3_STARTER / "tools" / "papers" / "tool.py").exists():
        raise FileNotFoundError(f"Day 3 starter not found at {DAY3_STARTER}; set DAY3_STARTER")
    if str(DAY3_STARTER) not in sys.path:
        sys.path.append(str(DAY3_STARTER))  # append: never shadow Day 7's own `src`
    from tools.github_search.tool import github_search
    from tools.papers.tool import arxiv_search
    return arxiv_search, github_search


def search_arxiv(query: str, max_results: int = 3) -> dict[str, Any]:
    arxiv_search, _ = _day3()
    r = arxiv_search(query=query, max_results=max(1, min(int(max_results or 3), 5)))
    if r.get("error"):
        return {"error": r["error"], "message": str(r.get("message", ""))[:200]}
    return {"items": [{"title": i["title"], "url": i["url"], "published": i["published"][:10],
                       "authors": i["authors"][:3], "summary": i["summary"][:350]} for i in r["items"]]}


def search_github(query: str, language: str = "", limit: int = 3) -> dict[str, Any]:
    _, github_search = _day3()
    r = github_search(query=query, sort="best_match", language=language or "", limit=max(1, min(int(limit or 3), 5)))
    if r.get("error"):
        return {"error": r["error"], "message": str(r.get("message", ""))[:200]}
    return {"items": [{"title": i["title"], "url": i["url"], "stars": i["stars"], "language": i["language"],
                       "description": (i["description"] or "")[:200]} for i in r["items"]]}
