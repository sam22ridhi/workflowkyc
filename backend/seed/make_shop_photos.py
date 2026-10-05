"""Printable SYNTHETIC shop images for demoing Drishti (contact point verification).

    python -m seed.make_shop_photos [output_dir]        default: seed/shop/

Makes a storefront with a signboard in English, in Hindi and in both, and a billing counter with a menu and a QR stand.
Print them on paper and hold them in front of the phone or laptop camera on the capture page. Do NOT show them on a screen: Drishti looks for the
pixel pattern of a photographed screen and will (correctly) flag it for a person to review. They are cartoons, not real photographs.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "shop"
EN_FONTS = ["C:/Windows/Fonts/ARIALNB.TTF", "C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/Library/Fonts/Arial Bold.ttf"]
HI_FONTS = ["C:/Windows/Fonts/Nirmala.ttc", "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf", "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
            "/Library/Fonts/Devanagari Sangam MN.ttc"]
rng = np.random.default_rng(3)


def font(candidates: list[str], size: int):
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def finish(img: Image.Image, path: Path):
    img = img.filter(ImageFilter.GaussianBlur(0.9))
    arr = np.asarray(img, float) + rng.normal(0, 4, (img.height, img.width, 3))
    Image.fromarray(np.clip(arr, 0, 255).astype("uint8")).save(path, "JPEG", quality=90)


def storefront(lines: list[tuple[str, list[str], int]], name: str):
    img = Image.new("RGB", (1280, 900), (176, 190, 200))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 620, 1280, 900], fill=(110, 110, 105))
    d.rectangle([140, 150, 1140, 640], fill=(214, 196, 170))
    d.rectangle([180, 360, 520, 640], fill=(70, 90, 110))
    d.rectangle([760, 360, 1100, 640], fill=(70, 90, 110))
    d.rectangle([200, 190, 1080, 330], fill=(18, 82, 40))
    d.rectangle([210, 200, 1070, 320], outline=(240, 240, 240), width=4)
    y = 215
    for text, fonts, size in lines:
        f = font(fonts, size)
        w = d.textlength(text, font=f)
        d.text(((1280 - w) / 2, y), text, font=f, fill=(255, 255, 255))
        y += size + 8
    finish(img, OUT / name)


def counter(name: str):
    img = Image.new("RGB", (1280, 900), (205, 190, 160))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 520, 1220, 900], fill=(120, 80, 50))
    d.rectangle([700, 140, 1180, 500], fill=(250, 245, 230), outline=(60, 40, 20), width=6)
    y = 160
    for line in ("MENU", "Masala Chai   Rs 20", "Veg Thali   Rs 120", "Samosa   Rs 15", "Cold Coffee   Rs 60"):
        d.text((730, y), line, font=font(EN_FONTS, 34), fill=(40, 20, 10))
        y += 62
    d.rectangle([180, 300, 420, 540], fill=(255, 255, 255), outline=(0, 0, 0), width=4)
    for i in range(14):
        for j in range(14):
            if rng.random() > 0.5:
                d.rectangle([200 + i * 14, 320 + j * 14, 212 + i * 14, 332 + j * 14], fill=(0, 0, 0))
    d.text((190, 548), "SCAN TO PAY", font=font(EN_FONTS, 36), fill=(255, 255, 255))
    finish(img, OUT / name)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    storefront([("SHARMA FOODS", EN_FONTS, 78)], "storefront_english_sign.jpg")
    storefront([("शर्मा फूड्स", HI_FONTS, 86)], "storefront_hindi_sign.jpg")
    storefront([("SHARMA FOODS", EN_FONTS, 60), ("शर्मा फूड्स", HI_FONTS, 56)], "storefront_both_scripts.jpg")
    counter("counter_menu_and_qr.jpg")
    print(f"Wrote 4 synthetic images to {OUT}. Print them; do not show them on a screen.")
