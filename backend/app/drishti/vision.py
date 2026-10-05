"""Image and text checks for Drishti. No multimodal model is used: Sarvam reads the text, local code does the rest.

name_match()      does the signboard text contain the trade name? (token coverage with fuzzy tolerance for OCR slips)
replay_score()    screen-replay heuristic: a photo of a screen shows periodic pixel-grid / moire peaks in the frequency spectrum
mcc_match()       do words read on the counter photo fit the declared merchant category code?
exif_info()       a browser-captured frame carries no camera EXIF block; a file taken from a gallery usually does

replay_score and mcc_match are ASSISTIVE: they are heuristics, they can be wrong, and a flag sends the case to a person.
"""
import io
import re
from difflib import SequenceMatcher

import numpy as np
from PIL import Image, ImageOps

# ---------------------------------------------------------------- signboard text
_STOP = {"pvt", "ltd", "private", "limited", "llp", "and", "the", "co", "company", "traders", "enterprises", "shop", "store"}


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+|[ऀ-ॿ]+", (text or "").lower()) if len(t) > 1 and t not in _STOP]


def name_match(trade_name: str, ocr_text: str) -> dict:
    """Coverage of the trade name's words in the signboard text. A word counts as present if it is in the text or within OCR-slip distance of
    a word that is. Devanagari signs cannot be matched to an English trade name automatically (no transliteration is done)."""
    want, have = _tokens(trade_name), _tokens(ocr_text)
    if not want:
        return {"score": 0.0, "found": [], "missing": [], "note": "No trade name on file to compare with."}
    found, missing = [], []
    for w in want:
        # an OCR slip (one wrong character) still counts, but the first letter must agree so 'foods' does not match 'goods'
        best = max((SequenceMatcher(None, w, h).ratio() for h in have if h[:1] == w[:1]), default=0.0)
        (found if (w in have or best >= 0.8 or w in "".join(have)) else missing).append(w)
    note = None
    if not found and any("ऀ" <= ch <= "ॿ" for ch in ocr_text or "") and not any("ऀ" <= ch <= "ॿ" for ch in trade_name or ""):
        note = "The signboard text is in Devanagari and the trade name is in English. Karyakarta does not transliterate, so a person should compare them."
    return {"score": round(len(found) / len(want), 2), "found": found, "missing": missing, "note": note}


# ---------------------------------------------------------------- screen replay (assistive)
CROSS_MASK = 8   # spectrum bins ignored around each axis. Without this, an ordinary storefront scored like a screen. Cost: a screen grid that is
                 # perfectly axis-aligned is not seen (off-axis moire, the usual case when a phone photographs a screen, is)


def replay_score(image_bytes: bytes) -> dict:
    """0..1. Looks for isolated, sharp peaks in the mid/high frequency spectrum, left after removing the smooth radial profile.
    Natural scenes have a smooth spectrum; a photographed screen adds regular peaks from the pixel grid and the moire it beats with the sensor.
    Textures with regular patterns (brick, fabric, grilles) can score high too, which is why a high score means 'a person should look', not 'fraud'."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("L")
    img.thumbnail((1024, 1024))
    a = np.asarray(img, dtype=np.float64)
    if min(a.shape) < 128:
        return {"score": 0.0, "peak_z": 0.0, "note": "Image too small to analyse."}
    a = a - a.mean()
    win = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    spec = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(a * win))))
    h, w = spec.shape
    yy, xx = np.indices(spec.shape)
    r = np.hypot((yy - h / 2) / (h / 2), (xx - w / 2) / (w / 2))                  # 0 at DC, 1 at the Nyquist edge of the short axis
    bins = np.minimum((r * 40).astype(int), 59)
    profile = np.array([spec[bins == b].mean() if np.any(bins == b) else 0.0 for b in range(60)])
    resid = spec - profile[bins]
    ring = (r > 0.12) & (r < 0.9)
    ring &= (np.abs(yy - h / 2) > CROSS_MASK) & (np.abs(xx - w / 2) > CROSS_MASK)   # long straight edges (shutters, signboards) load the two axes
    z = (resid[ring] - resid[ring].mean()) / (resid[ring].std() + 1e-9)
    peak_z = float(np.sort(z)[-5:].mean())                                          # mean of the five sharpest peaks
    score = float(np.clip((peak_z - 5.0) / 2.0, 0.0, 1.0))        # calibrated on SYNTHETIC images: edge-heavy storefronts <= 4.5, screen-like >= 7.5
    return {"score": round(score, 2), "peak_z": round(peak_z, 1)}


REPLAY_FLAG_AT = 0.5        # peak_z about 6.0. Not validated on real photographs: treat as a prompt for a person to look, never as proof


def exif_info(image_bytes: bytes) -> dict:
    """{has_camera_exif: bool, make, model}."""
    try:
        exif = Image.open(io.BytesIO(image_bytes)).getexif()
    except Exception:  # noqa: BLE001
        return {"has_camera_exif": False}
    make, model = exif.get(271), exif.get(272)
    return {"has_camera_exif": bool(make or model or exif.get(36867)), "make": make, "model": model}


def image_size(image_bytes: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(image_bytes)).size


# ---------------------------------------------------------------- MCC inventory (assistive)
MCC_KEYWORDS: dict[str, tuple[str, set[str]]] = {
    "5812": ("restaurants and eating places", {"menu", "thali", "chai", "tea", "coffee", "dosa", "idli", "pizza", "burger", "biryani", "paneer", "roti", "naan",
                                              "samosa", "sandwich", "juice", "lassi", "combo", "meal", "veg", "nonveg", "table", "restaurant", "cafe", "dhaba", "sweets"}),
    "5411": ("grocery stores", {"atta", "rice", "dal", "oil", "sugar", "salt", "flour", "biscuit", "soap", "grocery", "kirana", "masala", "milk", "bread", "per kg", "mrp"}),
    "5732": ("electronics", {"mobile", "phone", "laptop", "charger", "tv", "led", "headphone", "earphone", "speaker", "warranty", "electronics", "camera", "ac", "fridge"}),
    "5651": ("clothing", {"shirt", "saree", "kurta", "jeans", "trouser", "dress", "fabric", "garment", "tshirt", "lehenga", "size", "collection", "cloth"}),
    "5912": ("pharmacies", {"medicine", "tablet", "syrup", "pharmacy", "chemist", "capsule", "ointment", "rx", "drug", "health"}),
}
INDUSTRY_TO_MCC = {"food": "5812", "restaurant": "5812", "grocery": "5411", "electronics": "5732", "clothing": "5651", "pharmacy": "5912"}


def mcc_for(case_mcc: str | None, industry: str | None) -> str | None:
    return case_mcc or INDUSTRY_TO_MCC.get((industry or "").lower())


def mcc_match(mcc: str | None, ocr_text: str) -> dict:
    if not mcc or mcc not in MCC_KEYWORDS:
        return {"status": "skip", "note": "No merchant category code with a known keyword set for this case."}
    label, words = MCC_KEYWORDS[mcc]
    text = (ocr_text or "").lower()
    found = sorted(w for w in words if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", text))
    if not text.strip():
        return {"status": "warn", "label": label, "found": [], "note": "No readable text on the counter photo, so the inventory could not be compared with the category."}
    return {"status": "pass" if found else "warn", "label": label, "found": found,
            "note": None if found else f"None of the words expected for {label} were read on the counter photo."}
