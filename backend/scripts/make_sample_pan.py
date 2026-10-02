"""Generate a SYNTHETIC company PAN card image for testing extraction.

Fictional data, a fake-but-well-formed PAN, a SPECIMEN watermark, and no government
emblem or logo, so it can never be mistaken for a real card.

    python scripts/make_sample_pan.py                       # good card
    python scripts/make_sample_pan.py --name "Sharma Food"  # planted name mismatch
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def font(size, bold=False):
    names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", "Arial.ttf", "arial.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


ap = argparse.ArgumentParser()
ap.add_argument("--name", default="SHARMA FOODS PRIVATE LIMITED")
ap.add_argument("--pan", default="AABCS1429E")
ap.add_argument("--date", default="12/04/2021")
ap.add_argument("--out", default="samples/pan_sharma_foods.png")
a = ap.parse_args()

W, H = 1012, 638
img = Image.new("RGB", (W, H), (236, 244, 250))
d = ImageDraw.Draw(img)
d.rectangle([0, 0, W, 90], fill=(28, 74, 120))
d.text((30, 26), "PERMANENT ACCOUNT NUMBER CARD  (SAMPLE)", font=font(32, True), fill="white")

d.text((60, 140), "Permanent Account Number", font=font(24), fill=(60, 60, 60))
d.text((60, 172), a.pan, font=font(48, True), fill=(10, 10, 10))
d.text((60, 270), "Name", font=font(24), fill=(60, 60, 60))
d.text((60, 302), a.name, font=font(34, True), fill=(10, 10, 10))
d.text((60, 400), "Date of Incorporation/Formation", font=font(24), fill=(60, 60, 60))
d.text((60, 432), a.date, font=font(34, True), fill=(10, 10, 10))

# watermark
wm = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(wm).text((80, 520), "SPECIMEN - SYNTHETIC DEMO DATA", font=font(44, True), fill=(200, 0, 0, 120))
img = Image.alpha_composite(img.convert("RGBA"), wm).convert("RGB")

Path(a.out).parent.mkdir(parents=True, exist_ok=True)
img.save(a.out)
print("saved", a.out)
