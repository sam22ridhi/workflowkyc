"""Turns raw Sarvam responses into the field model the UI and checks use.

Field model (one entry per schema key):
    {value, confidence (0-100), page (1-based), box: {page,x,y,w,h} | None, box_source, [rows|boxes for lists]}
Boxes come ONLY from Sarvam `digitise` blocks (bbox_norm, 0-1 relative). Nothing is guessed: if a value can't be
matched to a block, box stays None and box_source "none".
"""
import re
from difflib import SequenceMatcher

# ---------------------------------------------------------------- extract results -> fields
def _is_leaf(a) -> bool:
    return isinstance(a, dict) and "confidence" in a


def _leaf_info(a) -> tuple[float | None, int | None]:
    conf = a.get("confidence")
    srcs = a.get("sources") or []
    page = srcs[0].get("page_num") if srcs and isinstance(srcs[0], dict) else None
    return (round(float(conf) * 100, 1) if isinstance(conf, (int, float)) else None), page


def _all_leaves(ann) -> list[dict]:
    if _is_leaf(ann):
        return [ann]
    if isinstance(ann, dict):
        return [x for v in ann.values() for x in _all_leaves(v)]
    if isinstance(ann, list):
        return [x for v in ann for x in _all_leaves(v)]
    return []


def to_fields(raw: dict, schema: dict) -> dict[str, dict]:
    result = raw.get("result") or {}
    ann = raw.get("annotations") or {}
    fields: dict[str, dict] = {}
    for key in schema["properties"]:
        value, a = result.get(key), ann.get(key)
        leaves = _all_leaves(a) if a is not None else []
        infos = [_leaf_info(x) for x in leaves]
        confs = [c for c, _ in infos if c is not None]
        pages = [p for _, p in infos if p]
        entry = {"value": value, "confidence": min(confs) if confs else None, "page": pages[0] if pages else None,
                 "box": None, "box_source": "none"}
        if isinstance(value, list) and isinstance(a, list) and a and all(isinstance(r, dict) and not _is_leaf(r) for r in a):
            # list of objects: per-row, per-leaf confidence. (List of plain strings has a leaf per item: no rows.)
            entry["rows"] = [
                {k: {"confidence": c, "page": p} for k, (c, p) in
                 ((k, _leaf_info(v)) for k, v in r.items() if _is_leaf(v))}
                for r in a
            ]
        fields[key] = entry
    return fields


def plain(fields: dict) -> dict:
    """{key: value} for the rule checks."""
    return {k: (v.get("value") if isinstance(v, dict) else v) for k, v in (fields or {}).items()}


# ---------------------------------------------------------------- digitise -> pages/blocks
def pages_from_digitise(raw: dict) -> list[dict]:
    pages = []
    for doc in raw.get("documents") or []:
        for pg in doc.get("pages") or []:
            blocks = []
            for b in pg.get("blocks") or []:
                bb = b.get("bbox_norm")
                if not bb or len(bb) != 4 or not (b.get("text") or "").strip():
                    continue
                text = _strip_html(b["text"]) if b.get("layout_tag") == "table" else b["text"]
                blocks.append({"id": b.get("block_id"), "text": text, "n": _norm(text), "layout": b.get("layout_tag"),
                               "bbox": [float(x) for x in bb], "order": b.get("reading_order") or 0})
            pages.append({"page": pg.get("page_num") or len(pages) + 1, "blocks": blocks})
    return pages


def _strip_html(html: str) -> str:
    """Digitise returns tables as one HTML block; keep just the cell text."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def digitise_text(raw: dict) -> str:
    return "\n".join(b["text"] for p in pages_from_digitise(raw) for b in p["blocks"])


# ---------------------------------------------------------------- locating values
def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _union(bboxes: list[list[float]]) -> list[float]:
    return [min(b[0] for b in bboxes), min(b[1] for b in bboxes), max(b[2] for b in bboxes), max(b[3] for b in bboxes)]


def _box(page: int, bb: list[float]) -> dict:
    return {"page": page, "x": round(bb[0], 5), "y": round(bb[1], 5),
            "w": round(bb[2] - bb[0], 5), "h": round(bb[3] - bb[1], 5)}


def _candidates(vn: str, blocks: list[dict]) -> list[dict]:
    """Blocks whose text contains the value (smallest first), else fuzzy matches."""
    hits = sorted((b for b in blocks if vn in b["n"]), key=lambda b: (len(b["n"]), b["order"]))
    if hits:
        return hits
    if len(vn) >= 6:
        fuzzy = [(SequenceMatcher(None, vn, b["n"]).ratio(), b) for b in blocks
                 if abs(len(b["n"]) - len(vn)) <= max(3, len(vn) // 5)]
        return [b for r, b in sorted(fuzzy, key=lambda t: -t[0]) if r >= 0.88]
    return []


def _multi_block(vn: str, blocks: list[dict]) -> list[dict]:
    """A value that wraps over several blocks (e.g. a multi-line address)."""
    parts = [b for b in sorted(blocks, key=lambda b: b["order"]) if len(b["n"]) >= 4 and b["n"] in vn]
    covered = sum(len(b["n"]) for b in parts)
    return parts if parts and 0.85 <= covered / max(len(vn), 1) <= 1.25 else []


def _pick(vn: str, page_blocks: list[dict], claimed: set[str]) -> tuple[list[float], list[str]] | None:
    if not vn:
        return None
    cands = _candidates(vn, page_blocks)
    free = [b for b in cands if b["id"] not in claimed]
    chosen = (free or cands)[:1]
    if not chosen:
        chosen = _multi_block(vn, page_blocks)
    if not chosen:
        return None
    return _union([b["bbox"] for b in chosen]), [b["id"] for b in chosen]


def _blocks_for(pages: list[dict], page: int | None) -> tuple[int, list[dict]] | None:
    for p in pages:
        if p["page"] == (page or 1):
            return p["page"], p["blocks"]
    return (pages[0]["page"], pages[0]["blocks"]) if pages else None


def _locate_rows(entry: dict, page_no: int, blocks: list[dict], claimed: set[str]) -> list[dict]:
    """Per-row boxes for list fields. Anchor each row on its most distinctive leaf, then take the other
    leaves from the same visual line so repeated values (40%, 'Sharma Holdings LLP') don't cross rows."""
    out = []
    for i, row in enumerate(entry["value"]):
        leaves = [(k, v) for k, v in row.items() if isinstance(v, str) and _norm(v)]
        if not leaves:
            continue
        counts = [(len(_candidates(_norm(v), blocks)) or 10 ** 6, n, k, v) for n, (k, v) in enumerate(leaves)]
        _, _, _, anchor_value = min(counts)
        anchor_hits = [b for b in _candidates(_norm(anchor_value), blocks)]
        free = [b for b in anchor_hits if b["id"] not in claimed] or anchor_hits
        if not free:
            continue
        anchor = free[0]
        if anchor.get("layout") == "table":
            # Sarvam gives no cell coordinates for tables; box the whole table, don't interpolate rows.
            out.append({"row": i, **_box(page_no, anchor["bbox"]), "precision": "table"})
            continue
        claimed.add(anchor["id"])
        ay0, ay1 = anchor["bbox"][1], anchor["bbox"][3]
        mid = (ay0 + ay1) / 2
        on_line = [b for b in blocks if b["bbox"][1] - 0.004 <= mid <= b["bbox"][3] + 0.004]
        boxes = [anchor["bbox"]]
        for k, v in leaves:
            vn = _norm(v)
            if vn and vn != _norm(anchor_value):
                hit = [b for b in on_line if vn in b["n"]]
                if hit:
                    boxes.append(min(hit, key=lambda b: len(b["n"]))["bbox"])
        out.append({"row": i, **_box(page_no, _union(boxes))})
    return out


def locate_boxes(fields: dict, digitise_raw: dict) -> dict:
    """Mutates and returns `fields`, adding box/box_source (and `boxes` for list fields)."""
    pages = pages_from_digitise(digitise_raw)
    claimed: set[str] = set()
    for entry in fields.values():
        value = entry.get("value")
        located = _blocks_for(pages, entry.get("page"))
        if located is None or value in (None, "", []):
            continue
        page_no, blocks = located
        if isinstance(value, list):
            rows = [r for r in value if isinstance(r, dict)]
            if rows:
                entry["boxes"] = _locate_rows({**entry, "value": rows}, page_no, blocks, claimed)
                if entry["boxes"]:
                    entry["box_source"] = "digitise"
                    if any(r.get("precision") == "table" for r in entry["boxes"]):
                        entry["box_precision"] = "table"
            continue
        hit = _pick(_norm(value), blocks, claimed)
        if hit:
            bb, ids = hit
            claimed.update(ids)
            entry["box"], entry["box_source"] = _box(page_no, bb), "digitise"
            if any(b.get("layout") == "table" for b in blocks if b["id"] in ids):
                entry["box_precision"] = "table"
    return fields


# ---------------------------------------------------------------- cheap document-type classifier
_CLASS_RULES: list[tuple[str, list[str]]] = [
    ("gst", ["reg-06", "goods and services tax", "gstin", "registration certificate"]),
    ("coi", ["certificate of incorporation", "corporate identity number"]),
    ("board_resolution", ["board resolution", "resolved that", "resolved further"]),
    ("shareholding", ["shareholding", "beneficial owner", "shareholders"]),
    ("fssai", ["fssai", "food safety and standards"]),
    ("bank_cheque", ["cheque", "ifsc", "account number", "bank letter"]),
    ("director_kyc", ["aadhaar", "identity proof", "passport", "voter", "driving licence", "driving license"]),
    ("pan", ["permanent account number", "income tax department"]),
]


def classify_text(text: str) -> tuple[str, int]:
    """Keyword scoring over OCR text. Returns (doc_type, hits); ('unknown', 0) when nothing matches."""
    t = text.lower()
    scored = [(sum(1 for kw in kws if kw in t), dt) for dt, kws in _CLASS_RULES]
    best = max(scored)
    return (best[1], best[0]) if best[0] else ("unknown", 0)
