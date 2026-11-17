"""Multimodal retrieval: one ranked list over text chunks (book_chunks) AND visual chunks (book_visual).

  MultiStoreDense  embeds the query once (e5 "query:"), searches both pgvector tables and merges by cosine
                   score (same model and metric on both sides, so scores are comparable).
  BM25             the stage-2 BM25 with syllable bigrams, over text + visual chunk texts.
  hybrid           RRF of the two (same HybridRetriever as stage 2), more candidates per side.
Every result keeps id/page/metadata; visual results carry bbox + crop for verification.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from src.retrieval import BM25Retriever, HybridRetriever, check_filters, load_chunks

DAY7 = Path(__file__).resolve().parents[2]


def load_visual_chunks() -> list[dict[str, Any]]:
    return json.loads((DAY7 / "data" / "advanced" / "visual_chunks.json").read_text(encoding="utf-8"))


class MultiStoreDense:
    name = "dense_mm"

    def __init__(self) -> None:
        from src.day6_bridge import connect
        self.embedder, text_store = connect()
        BookStore = importlib.import_module("day6src.book_store").BookStore
        visual_store = BookStore(text_store.database_url, self.embedder.dimensions, self.embedder.model_name, table="book_visual")
        self.stores = [text_store, visual_store]

    def search(self, query: str, *, filters: dict[str, Any] | None = None, top_k: int = 3) -> list[dict[str, Any]]:
        check_filters(filters)
        vec = self.embedder.embed_query(query)
        merged = [r for s in self.stores for r in s.search(vec, top_k=top_k, filters=filters)]
        merged.sort(key=lambda r: (-r["score"], r["id"]))
        return [{**r, "rank": i + 1, "strategy": self.name} for i, r in enumerate(merged[:top_k])]


def make_mm_retriever(kind: str = "mm_hybrid"):
    """kind: mm_dense | mm_bm25 | mm_hybrid | text_hybrid (stage-2 hybrid over text only, for ablation)"""
    text = load_chunks()
    if kind == "text_hybrid":
        from src.retrieval import DenseRetriever
        return HybridRetriever(DenseRetriever(), BM25Retriever(text, ngram=2))
    allc = text + load_visual_chunks()
    if kind == "mm_bm25":
        return BM25Retriever(allc, ngram=2)
    dense = MultiStoreDense()
    if kind == "mm_dense":
        return dense
    if kind == "mm_hybrid":
        return HybridRetriever(dense, BM25Retriever(allc, ngram=2), candidates=30)
    raise ValueError(f"unknown multimodal retriever {kind!r}")
