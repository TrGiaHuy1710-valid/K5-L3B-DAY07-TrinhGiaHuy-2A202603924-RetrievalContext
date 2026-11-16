"""Export the Day 6 `book_chunks` table to data/book/chunks.json (Day 7 chunk schema) and sanity-check dense search.

Run from the Day 7 repo root:  python -m src.export_chunks
"""
from __future__ import annotations

import json
import sys

from src.day6_bridge import DAY7, connect


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    embedder, store = connect()
    chunks = store.all_chunks()
    if not chunks:
        raise RuntimeError("book_chunks is empty: run `python -m src.book_ingest` in Day 6 first")
    out = DAY7 / "data" / "book"
    out.mkdir(parents=True, exist_ok=True)
    (out / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    pages = sorted({c["page"] for c in chunks})
    print(f"exported {len(chunks)} chunks, pages {pages[0]}-{pages[-1]} ({len(pages)} pages) -> {out / 'chunks.json'}")
    print(f"embedder={embedder.model_name} dim={embedder.dimensions}")

    # connection sanity check: the query embedding must be compatible with the stored vectors
    for q in ("hàm mất mát của hồi quy tuyến tính", "ước lượng hợp lý cực đại là gì"):
        hits = store.search(embedder.embed_query(q), top_k=3)
        print(f"\nQ: {q}")
        for h in hits:
            print(f"  {h['score']:.3f} p{h['page']} {h['metadata']['chapter']} | {h['text'][:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
