"""Step 3: turn described regions into searchable "visual chunks" and index them next to the text chunks.

    python -m src.advanced.mm_index      -> data/advanced/visual_chunks.json + pgvector table `book_visual`

A visual chunk = caption + vision description, with provenance back to the original page:
  id = book-ml-co-ban|p104|v00, page, metadata {kind: visual, vtype, caption_label, related_caption,
  bbox (PDF points), crop (PNG path), chapter_no/chapter/section copied from the text chunks of that page}.
Embedded with the SAME e5 model as the text index (Day 6 embedder + cache) so scores are comparable.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

from src.day6_bridge import _load_day6

DAY7 = Path(__file__).resolve().parents[2]
ADV = DAY7 / "data" / "advanced"
TABLE = "book_visual"
TYPE_VI = {"table": "Bảng", "chart": "Biểu đồ", "diagram": "Sơ đồ", "image": "Ảnh", "formula": "Công thức", "other": "Hình"}


def build_visual_chunks() -> list[dict]:
    regions = json.loads((ADV / "regions.json").read_text(encoding="utf-8"))["regions"]
    desc = json.loads((ADV / "descriptions.json").read_text(encoding="utf-8"))
    text_chunks = json.loads((DAY7 / "data" / "book" / "chunks.json").read_text(encoding="utf-8"))
    page_meta = {}
    for c in text_chunks:
        page_meta.setdefault(c["page"], c["metadata"])
    out = []
    for r in regions:
        d = desc.get(r["id"])
        if r["skip_vision"] or not d or d.get("error"):
            continue
        vtype = d["type"] if d["type"] in TYPE_VI else "other"
        head = r["caption"] or (f"(hình con, thuộc {r['related_caption']})" if r["related_caption"] else "")
        md = page_meta.get(r["page"], {})
        # index v2 (dev error ad12): put the chapter in the searchable text, so questions that locate a figure by
        # chapter ("hình ở đầu chương SVM") can match it; v1 had the chapter only in metadata
        where = f"Chương {md.get('chapter_no', '')}: {md.get('chapter', '')}" + (f" · {md['section']}" if md.get("section") else "")
        text = f"{TYPE_VI[vtype]} trang {r['page']} ({where}). {head}\n{d.get('title', '')}\n{d['content']}".strip()
        out.append({"id": r["id"], "source_id": "book-ml-co-ban", "source": "book_ML.pdf", "page": r["page"], "text": text,
                    "metadata": {"kind": "visual", "vtype": vtype, "caption_label": r["caption_label"],
                                 "related_caption": r["related_caption"], "bbox": r["bbox"], "crop": r["crop"],
                                 "part": md.get("part", ""), "chapter_no": md.get("chapter_no", ""),
                                 "chapter": md.get("chapter", ""), "section": md.get("section", ""),
                                 "described_by": d.get("model", ""), "index_version": 2}})
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    chunks = build_visual_chunks()
    (ADV / "visual_chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    _load_day6()
    emb_mod = importlib.import_module("day6src.embeddings")
    Chunk = importlib.import_module("day6src.models").Chunk
    BookStore = importlib.import_module("day6src.book_store").BookStore
    db_url = importlib.import_module("day6src.store").database_url_from_env()
    embedder = emb_mod.make_embedder()
    objs = [Chunk(c["id"], c["source_id"], c["source"], c["page"], c["text"], c["metadata"]) for c in chunks]
    vectors, rep = emb_mod.embed_strategy("VISUAL", objs, embedder)
    store = BookStore(db_url, embedder.dimensions, embedder.model_name, table=TABLE)
    store.create_schema()
    db = store.upsert(objs, vectors)
    from collections import Counter
    print({"visual_chunks": len(chunks), "types": dict(Counter(c["metadata"]["vtype"] for c in chunks)),
           "embedded": rep["embedded"], "truncated": rep["truncated_inputs"], "db": db})
    return 0


if __name__ == "__main__":
    sys.exit(main())
