"""Drishti building blocks: distance, name matching, screen-replay heuristic, MCC words, EXIF."""
import io

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter

from app.drishti import geo, vision


def _scene(seed: int, w=1400, h=1000):
    rng = np.random.default_rng(seed)
    base = Image.fromarray((rng.random((h // 40, w // 40)) * 255).astype("uint8")).resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(5))
    d = ImageDraw.Draw(base)
    for _ in range(10):
        x, y = int(rng.integers(0, w - 220)), int(rng.integers(0, h - 140))
        d.rectangle([x, y, x + int(rng.integers(40, 220)), y + int(rng.integers(30, 140))], outline=int(rng.integers(0, 255)), width=3, fill=int(rng.integers(40, 220)))
    return np.asarray(base, float) + rng.normal(0, 6, (h, w))


def _jpeg(a, **kw):
    b = io.BytesIO()
    Image.fromarray(np.clip(a, 0, 255).astype("uint8")).save(b, "JPEG", quality=88, **kw)
    return b.getvalue()


def test_haversine_known_distances():
    assert geo.haversine_m(19.0760, 72.8777, 19.0760, 72.8777) == 0
    assert geo.haversine_m(19.0760, 72.8777, 19.0769, 72.8777) == pytest.approx(100, abs=2)          # 0.0009 degrees of latitude
    assert geo.haversine_m(19.0760, 72.8777, 28.6139, 77.2090) == pytest.approx(1_153_000, rel=0.01)   # Mumbai to Delhi
    assert geo.haversine_m(0, 0, 0, 1) == pytest.approx(111_195, rel=0.001)


@pytest.mark.parametrize("trade,ocr,expect_found,expect_missing", [
    ("Sharma Foods", "SHARMA FOODS\nPure Veg Restaurant", ["sharma", "foods"], []),
    ("Sharma Foods Pvt Ltd", "Sharma Food5 Ph 98xxx", ["sharma", "foods"], []),                      # an OCR slip (5 for s) is tolerated
    ("Sharma Foods", "SHARMA STORES", ["sharma"], ["foods"]),
    ("Sharma Foods", "Sharma Goods", ["sharma"], ["foods"]),                                           # one letter off is not an OCR slip when the first letter differs
    ("Sharma Foods", "Royal Rajasthan Spices", [], ["sharma", "foods"]),
])
def test_signboard_name_match(trade, ocr, expect_found, expect_missing):
    m = vision.name_match(trade, ocr)
    assert m["found"] == expect_found and m["missing"] == expect_missing
    assert m["score"] == round(len(expect_found) / (len(expect_found) + len(expect_missing)), 2)


def test_devanagari_sign_for_an_english_name_asks_for_a_person():
    m = vision.name_match("Sharma Foods", "शर्मा फूड्स")
    assert m["score"] == 0.0 and "does not transliterate" in m["note"]
    assert vision.name_match("शर्मा फूड्स", "शर्मा फूड्स भोजनालय")["score"] == 1.0


def test_screen_replay_heuristic_separates_screen_like_images_on_synthetic_data():
    natural = [vision.replay_score(_jpeg(_scene(s)))["score"] for s in range(4)]
    assert max(natural) < vision.REPLAY_FLAG_AT
    yy, xx = np.indices((1000, 1400))
    for period, amp in ((3, 8), (4, 8), (5, 12), (6, 12)):
        a = _scene(11) + amp * np.sin(2 * np.pi * xx / period) * np.sin(2 * np.pi * yy / period) + 0.6 * amp * np.sin(2 * np.pi * (xx * 0.93 + yy * 0.31) / (period * 1.3))
        assert vision.replay_score(_jpeg(a))["score"] >= vision.REPLAY_FLAG_AT, (period, amp)
    assert vision.replay_score(_jpeg(np.zeros((60, 60))))["note"] == "Image too small to analyse."


def test_an_edge_heavy_storefront_is_not_mistaken_for_a_screen():
    """Regression: long straight edges (shutters, signboards) used to score like a photographed screen (live run, 2026-10-03)."""
    rng = np.random.default_rng(42)
    img = Image.new("RGB", (1280, 900), (176, 190, 200))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 620, 1280, 900], fill=(110, 110, 105))
    d.rectangle([140, 150, 1140, 640], fill=(214, 196, 170))
    d.rectangle([200, 190, 1080, 330], fill=(18, 82, 40), outline=(240, 240, 240), width=4)
    d.rectangle([180, 360, 520, 640], fill=(70, 90, 110))
    d.rectangle([760, 360, 1100, 640], fill=(70, 90, 110))
    for i in range(8):
        d.line([(190, 380 + i * 14), (510, 380 + i * 14)], fill=(30, 40, 50), width=2)                  # shutter slats
    arr = np.asarray(img.filter(ImageFilter.GaussianBlur(0.9)).convert("L"), float) + rng.normal(0, 4, (900, 1280))
    assert vision.replay_score(_jpeg(arr))["score"] < vision.REPLAY_FLAG_AT


def test_mcc_keywords_and_industry_mapping():
    assert vision.mcc_for(None, "food") == "5812" and vision.mcc_for("5732", "food") == "5732" and vision.mcc_for(None, "software") is None
    ok = vision.mcc_match("5812", "MENU\nMasala Chai 20\nVeg Thali 120")
    assert ok["status"] == "pass" and {"menu", "chai", "thali"} <= set(ok["found"])
    assert vision.mcc_match("5812", "Mobile Charger Laptop Warranty")["status"] == "warn"
    assert vision.mcc_match("5812", "   ")["status"] == "warn" and vision.mcc_match(None, "x")["status"] == "skip"
    assert vision.mcc_match("5812", "teapot")["status"] == "warn"                                     # whole words only


def test_exif_detection_and_size():
    plain = _jpeg(_scene(1))
    assert vision.exif_info(plain)["has_camera_exif"] is False
    exif = Image.Exif()
    exif[271], exif[272] = "Apple", "iPhone 13"
    tagged = _jpeg(_scene(1), exif=exif.tobytes())
    info = vision.exif_info(tagged)
    assert info["has_camera_exif"] and info["make"] == "Apple"
    assert vision.image_size(plain) == (1400, 1000)
    assert vision.exif_info(b"not an image") == {"has_camera_exif": False}
