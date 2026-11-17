"""Step 1 of the advanced (multimodal) pipeline: find visual regions on every indexed page and crop them.

    python -m src.advanced.visual_extract            -> data/advanced/regions.json + data/advanced/crops/*.png

A "visual region" = union of nearby graphic elements on a page:
  * raster images        (page.get_image_info)   -> photos, plotted charts exported as images
  * vector drawing groups (page.cluster_drawings) -> LaTeX/TikZ diagrams, charts, table rules
Elements closer than MERGE_GAP points are merged (sub-figures (a)(b) become one region). Thin lines
(rules), tiny boxes and code listings (text inside mostly in the monospace font VnNimbusMonoL; already
indexed as text) are dropped. Each region is linked to the nearest caption "Hình x.y." / "Bảng x.y:" and
cropped from the ORIGINAL PDF (caption included) so the vision model and the grader see the real figure.
Captions that get no region are reported (coverage), never silently ignored.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

DAY7 = Path(__file__).resolve().parents[2]
PDF = DAY7.parent / "book_ML.pdf"
OUT = DAY7 / "data" / "advanced"
DOC_ID = "book-ml-co-ban"
FIRST, LAST = 15, 404          # same body range as the text index
MERGE_GAP = 8.0                # points
MIN_AREA, MIN_SIDE = 1800.0, 12.0
CAPTION_MAX_DIST = 140.0
ZOOM = 2.5
TEXT_BOX_CHARS = 150
CAPTION = re.compile(r"^(Hình|Bảng)\s*(\d+\.\d+)\s*[.:]\s*(.*)$", re.S)
MONO = "NimbusMono"


def _rect(t):
    return [float(t[0]), float(t[1]), float(t[2]), float(t[3])]


def _gap(a, b) -> float:
    dx = max(b[0] - a[2], a[0] - b[2], 0.0)
    dy = max(b[1] - a[3], a[1] - b[3], 0.0)
    return max(dx, dy) if (dx == 0 or dy == 0) else (dx * dx + dy * dy) ** 0.5


def _union(a, b):
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def merge(rects: list[list[float]]) -> list[list[float]]:
    rects = [r[:] for r in rects]
    changed = True
    while changed:
        changed = False
        out: list[list[float]] = []
        for r in rects:
            for o in out:
                if _gap(r, o) <= MERGE_GAP:
                    o[:] = _union(o, r)
                    changed = True
                    break
            else:
                out.append(r)
        rects = out
    return rects


def _inside_text(page_dict, r):
    """(chars in monospace font, all chars) of spans whose centre lies inside r."""
    mono = total = 0
    for b in page_dict["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                x0, y0, x1, y1 = s["bbox"]
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                if r[0] <= cx <= r[2] and r[1] <= cy <= r[3]:
                    n = len(s["text"].strip())
                    total += n
                    mono += n if MONO in s["font"] else 0
    return mono, total


def captions(page) -> list[dict]:
    out = []
    for b in page.get_text("blocks"):
        text = " ".join(b[4].split())
        m = CAPTION.match(text)
        if m:
            out.append({"kind": "table" if m.group(1) == "Bảng" else "figure", "label": f"{m.group(1)} {m.group(2)}",
                        "text": text[:400], "bbox": _rect(b[:4])})
    return out


def regions_on_page(page) -> tuple[list[dict], list[dict]]:
    elems = [_rect(i["bbox"]) for i in page.get_image_info()]
    try:
        elems += [_rect(r) for r in page.cluster_drawings()]
    except Exception:
        pass
    pd = page.get_text("dict")
    regions = []
    for r in merge(elems):
        w, h = r[2] - r[0], r[3] - r[1]
        if w < MIN_SIDE or h < MIN_SIDE or w * h < MIN_AREA:
            continue
        mono, total = _inside_text(pd, r)
        if total and mono / total > 0.5:
            continue  # code listing frame: its text is already in the text index
        regions.append({"bbox": [round(v, 1) for v in r], "text_chars": total})
    caps = captions(page)
    # every caption goes to its nearest region (a merged group of sub-figures may own several captions)
    orphan_caps = []
    for c in caps:
        # LaTeX layout of this book: a figure caption sits BELOW (or beside) its figure, a table caption ABOVE its
        # table. Prefer regions on the correct side; fall back to the nearest region only if none qualifies.
        def side_ok(rg, c=c):
            r, b = rg["bbox"], c["bbox"]
            beside = r[1] < b[3] and b[1] < r[3]
            return beside or (r[3] <= b[1] + 6 if c["kind"] == "figure" else r[1] >= b[3] - 6)
        cand = [(_gap(rg["bbox"], c["bbox"]), i) for i, rg in enumerate(regions) if side_ok(rg)]
        best = min(cand or [(_gap(rg["bbox"], c["bbox"]), i) for i, rg in enumerate(regions)], default=(None, None))
        if best[0] is None or best[0] > CAPTION_MAX_DIST:
            orphan_caps.append(c)
        else:
            regions[best[1]].setdefault("captions", []).append(c)
    # sub-figures without their own caption: remember the nearest caption on the page (same figure, usually)
    for rg in regions:
        if not rg.get("captions") and caps:
            rg["related_caption"] = min(caps, key=lambda c: _gap(rg["bbox"], c["bbox"]))["label"]
    return regions, orphan_caps


def main() -> int:
    import pymupdf
    sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.perf_counter()
    doc = pymupdf.open(PDF)
    crops = OUT / "crops"
    crops.mkdir(parents=True, exist_ok=True)
    all_regions, orphans = [], []
    for pno in range(FIRST, LAST + 1):
        page = doc[pno - 1]
        regs, orph = regions_on_page(page)
        orphans += [{"page": pno, **c} for c in orph]
        regs.sort(key=lambda r: (r["bbox"][1], r["bbox"][0]))
        for i, rg in enumerate(regs):
            caps = rg.get("captions", [])
            box = rg["bbox"]
            for c in caps:
                box = _union(box, c["bbox"])
            clip = pymupdf.Rect(box[0] - 4, box[1] - 4, box[2] + 4, box[3] + 4) & page.rect
            rid = f"{DOC_ID}|p{pno:03d}|v{i:02d}"
            path = crops / f"p{pno:03d}_v{i:02d}.png"
            page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), clip=clip, alpha=False).save(path)
            all_regions.append({"id": rid, "page": pno, "bbox": rg["bbox"], "crop_bbox": [round(v, 1) for v in clip],
                                "crop": f"data/advanced/crops/{path.name}", "caption_label": "; ".join(c["label"] for c in caps),
                                "caption_kind": caps[0]["kind"] if caps else "", "caption": " | ".join(c["text"] for c in caps),
                                "related_caption": rg.get("related_caption", ""), "text_chars": rg["text_chars"],
                                # uncaptioned box full of prose (definition/theorem/formula frame): text already indexed
                                "skip_vision": (not caps) and rg["text_chars"] > TEXT_BOX_CHARS})
    stats = {"pages": f"{FIRST}-{LAST}", "regions": len(all_regions),
             "with_caption": sum(bool(r["caption_label"]) for r in all_regions),
             "captions_linked": sum(len(r["caption_label"].split("; ")) for r in all_regions if r["caption_label"]),
             "tables_captioned": sum(r["caption_kind"] == "table" for r in all_regions),
             "figures_captioned": sum(r["caption_kind"] == "figure" for r in all_regions),
             "text_boxes_skipped": sum(r["skip_vision"] for r in all_regions),
             "orphan_captions": len(orphans), "seconds": round(time.perf_counter() - t0, 1)}
    (OUT / "regions.json").write_text(json.dumps({"stats": stats, "regions": all_regions, "orphan_captions": orphans},
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print(stats)
    for o in orphans:
        print("  caption without region:", o["page"], o["label"], o["text"][:70])
    return 0


if __name__ == "__main__":
    sys.exit(main())
