"""Generates the realistic-looking SYNTHETIC document pack for the Sharma Foods demo (reportlab, vector PDFs with a real text layer).

Looks like the paperwork a KAM actually receives: letterheads, bordered government-style forms, a cheque leaf with MICR band, an ID card,
company seals, signatures and "certified true copy" stamps. What it deliberately does NOT have: government emblems or logos, holograms, QR codes
or any security feature, and every page carries a diagonal "SPECIMEN - SYNTHETIC DEMO DATA" watermark and a footer saying so. All names and numbers are fictional.

The pack contains the same four planted problems as the test set (seed/make_docs.py):
  1. cheque account name "Sharma Foods" != legal name "Sharma Foods Private Limited"
  2. board resolution signatory (Ravish Sahay) is not a current director (MCA: Anil Sharma, Priya Sharma)
  3. hidden beneficial owner: Sharma Holdings LLP owns 30%, Rakesh Sharma holds 60% of it -> 18% effective
  4. address drift: GST principal place and electricity bill say Navi Mumbai, the application says Mumbai
Output is byte-for-byte deterministic (reportlab invariant mode), so recorded Sarvam results in demo_cache/ match on any machine.
The all-correct set (seed/demo_pack_correct, 12 documents) has no planted problem: it is the happy path.
The fix pack (seed/demo_pack/fixes) is what the merchant uploads live to clear the issues they can fix: a corrected cheque and the KYC of the other owners.
Usage: python -m seed.make_realistic_docs [output_dir]      (default: seed/demo_pack)
"""
import math
import random
import sys
from pathlib import Path

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

W, H = A4
INK = HexColor("#1b2a6b")          # blue-black ink for stamps and signatures
GREY = HexColor("#5b6070")
LINE = HexColor("#9aa0b4")


# ------------------------------------------------------------------ primitives
def new(path: Path) -> canvas.Canvas:
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    c.setTitle(path.stem.replace("_", " "))
    c.setAuthor("Synthetic specimen")
    return c


def specimen(c: canvas.Canvas) -> None:
    """Diagonal watermark (twice) and a footer. Drawn last so it sits over the page like a real overprint."""
    c.saveState()
    c.setFillColor(Color(0.55, 0.55, 0.62, alpha=0.16))
    c.setFont("Helvetica-Bold", 34)
    for cy in (H * 0.30, H * 0.68):
        c.saveState()
        c.translate(W / 2, cy)
        c.rotate(33)
        c.drawCentredString(0, 0, "SPECIMEN - SYNTHETIC DEMO DATA")
        c.restoreState()
    c.setFillColor(GREY)
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(W / 2, 18, "Synthetic specimen created for a software demonstration. Fictional names and numbers. Not a valid document.")
    c.restoreState()


def gradient(c, x, y, w, h, top, bottom, steps=40):
    for i in range(steps):
        t = i / (steps - 1)
        c.setFillColorRGB(*(top[k] + (bottom[k] - top[k]) * t for k in range(3)))
        c.rect(x, y + h - (i + 1) * h / steps, w, h / steps + 0.6, stroke=0, fill=1)


def wave_pattern(c, x, y, w, h, color, n=14, amp=5, alpha=0.5):
    """Decorative guilloche-like background lines (just ornament; no security meaning)."""
    c.saveState()
    c.setStrokeColor(Color(color[0], color[1], color[2], alpha=alpha))
    c.setLineWidth(0.4)
    p = c.beginPath()
    p.rect(x, y, w, h)
    c.clipPath(p, stroke=0, fill=0)
    for k in range(n):
        yy = y + k * h / n
        path = c.beginPath()
        path.moveTo(x, yy)
        for i in range(0, int(w) + 4, 4):
            path.lineTo(x + i, yy + amp * math.sin(i / 14.0 + k * 0.7))
        c.drawPath(path, stroke=1, fill=0)
    c.restoreState()


def signature(c, x, y, seed: int, width=90, height=26):
    """A handwritten-looking scribble: connected loops drawn with bezier curves."""
    rng = random.Random(seed)
    c.saveState()
    c.setStrokeColor(INK)
    c.setLineWidth(1.1)
    p = c.beginPath()
    p.moveTo(x, y)
    cx, cy = x, y
    steps = 7
    for i in range(steps):
        nx = x + (i + 1) * width / steps
        ny = y + rng.uniform(-height / 2, height / 2)
        p.curveTo(cx + rng.uniform(4, 14), cy + rng.uniform(-height, height), nx - rng.uniform(4, 14), ny + rng.uniform(-height, height), nx, ny)
        cx, cy = nx, ny
    c.drawPath(p, stroke=1, fill=0)
    c.setLineWidth(0.8)
    c.line(x + 6, y - height / 2 - 2, x + width * 0.9, y - height / 2 + 4)
    c.restoreState()


def seal(c, cx, cy, r, top: str, bottom: str, rotate=0, mark: str = "SFPL"):
    """A round company seal in ink."""
    c.saveState()
    c.translate(cx, cy)
    c.rotate(rotate)
    c.setStrokeColor(Color(0.1, 0.17, 0.55, alpha=0.85))
    c.setFillColor(Color(0.1, 0.17, 0.55, alpha=0.85))
    c.setLineWidth(1.6)
    c.circle(0, 0, r, stroke=1, fill=0)
    c.setLineWidth(0.7)
    c.circle(0, 0, r - 5, stroke=1, fill=0)
    c.circle(0, 0, r * 0.45, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 6.2)
    n = len(top)
    for i, ch in enumerate(top):                       # text around the upper arc
        a = math.radians(160 - i * (140.0 / max(n - 1, 1)))
        c.saveState()
        c.translate((r - 12) * math.cos(a), (r - 12) * math.sin(a))
        c.rotate(math.degrees(a) - 90)
        c.drawCentredString(0, 0, ch)
        c.restoreState()
    m = len(bottom)
    for i, ch in enumerate(bottom):                    # and the lower arc
        a = math.radians(200 + i * (140.0 / max(m - 1, 1)))
        c.saveState()
        c.translate((r - 12) * math.cos(a), (r - 12) * math.sin(a))
        c.rotate(math.degrees(a) + 90)
        c.drawCentredString(0, 0, ch)
        c.restoreState()
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(0, -3, mark)
    c.restoreState()


def stamp_box(c, x, y, w, h, text, rotate=-6, color=None):
    c.saveState()
    c.translate(x + w / 2, y + h / 2)
    c.rotate(rotate)
    c.setStrokeColor(color or Color(0.75, 0.1, 0.15, alpha=0.8))
    c.setFillColor(color or Color(0.75, 0.1, 0.15, alpha=0.8))
    c.setLineWidth(1.6)
    c.roundRect(-w / 2, -h / 2, w, h, 3, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 11)
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        c.drawCentredString(0, (len(lines) - 1) * 6 - i * 13 - 3, ln)
    c.restoreState()


def text(c, x, y, s, font="Helvetica", size=10, color=None, align="left"):
    c.setFont(font, size)
    c.setFillColor(color or HexColor("#111111"))
    {"left": c.drawString, "center": c.drawCentredString, "right": c.drawRightString}[align](x, y, s)


def para(c, x, y, s, font="Times-Roman", size=10.5, width=480, leading=15, color=None):
    """Wrapped paragraph; returns the y below it."""
    for ln in simpleSplit(s, font, size, width):
        text(c, x, y, ln, font, size, color)
        y -= leading
    return y


def grid(c, x, top, col_w, rows, row_h=24, header=True, size=9.5, shade=HexColor("#eef0f7"), bold_first_col=False, pad=6):
    """A bordered table. rows is a list of lists of strings. Returns the y of the table bottom."""
    total_w = sum(col_w)
    y = top
    for ri, row in enumerate(rows):
        h = row_h
        if header and ri == 0:
            c.setFillColor(shade)
            c.rect(x, y - h, total_w, h, stroke=0, fill=1)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.rect(x, y - h, total_w, h, stroke=1, fill=0)
        cx = x
        for ci, cell in enumerate(row):
            if ci:
                c.line(cx, y, cx, y - h)
            bold = (header and ri == 0) or (bold_first_col and ci == 0)
            text(c, cx + pad, y - h / 2 - size / 3, cell, "Helvetica-Bold" if bold else "Helvetica", size)
            cx += col_w[ci]
        y -= h
    return y


def letterhead(c, name: str, lines: list[str], color=HexColor("#7a1f2b")):
    c.setFillColor(color)
    c.rect(0, H - 14, W, 14, stroke=0, fill=1)
    text(c, 50, H - 52, name, "Times-Bold", 21, color)
    for i, ln in enumerate(lines):
        text(c, 50, H - 68 - i * 11, ln, "Helvetica", 8, GREY)
    c.setStrokeColor(color)
    c.setLineWidth(1.2)
    c.line(50, H - 68 - len(lines) * 11 - 2, W - 50, H - 68 - len(lines) * 11 - 2)
    return H - 68 - len(lines) * 11 - 24


# ------------------------------------------------------------------ the documents
def pan(path: Path):
    c = new(path)
    x, y, w, h = 70, H - 330, W - 140, 250                                     # the card
    c.setFillColor(HexColor("#e9e4d6"))
    c.roundRect(x - 6, y - 6, w + 12, h + 12, 14, stroke=0, fill=1)            # card shadow / edge
    gradient(c, x, y, w, h, (0.86, 0.91, 0.97), (0.96, 0.93, 0.86))
    wave_pattern(c, x, y, w, h, (0.45, 0.55, 0.78), n=22, amp=6, alpha=0.35)
    c.setFillColor(HexColor("#1e3a8a"))
    c.rect(x, y + h - 46, w, 46, stroke=0, fill=1)
    text(c, x + 18, y + h - 20, "INCOME TAX DEPARTMENT", "Helvetica-Bold", 14, HexColor("#ffffff"))
    text(c, x + 18, y + h - 36, "Permanent Account Number Card (specimen format)", "Helvetica", 8.5, HexColor("#dbe4ff"))
    text(c, x + w - 18, y + h - 28, "PAN", "Helvetica-Bold", 22, HexColor("#ffffff"), "right")
    text(c, x + 24, y + h - 78, "Permanent Account Number", "Helvetica", 8.5, GREY)
    text(c, x + 24, y + h - 100, "AABCS1429E", "Courier-Bold", 25)
    text(c, x + 24, y + h - 130, "Name", "Helvetica", 8.5, GREY)
    text(c, x + 24, y + h - 148, "SHARMA FOODS PRIVATE LIMITED", "Helvetica-Bold", 14)
    text(c, x + 24, y + h - 176, "Date of Incorporation / Formation", "Helvetica", 8.5, GREY)
    text(c, x + 24, y + h - 193, "14/08/2021", "Helvetica-Bold", 13)
    c.setStrokeColor(LINE)
    c.rect(x + w - 150, y + 24, 126, 54, stroke=1, fill=0)
    text(c, x + w - 87, y + 14, "Signature / Authorised signatory", "Helvetica", 6.5, GREY, "center")
    signature(c, x + w - 135, y + 52, 11, width=95, height=14)
    text(c, 70, y - 34, "In case this card is lost / found, please inform / return to the Income Tax PAN Services Unit.", "Helvetica", 8, GREY)
    text(c, 70, y - 48, "Card layout is a specimen created for a demonstration; it is not issued by any authority.", "Helvetica-Oblique", 8, GREY)
    specimen(c)
    c.save()


def gst(path: Path):
    c = new(path)
    c.setFillColor(HexColor("#0f3d6e"))
    c.rect(0, H - 92, W, 92, stroke=0, fill=1)
    text(c, W / 2, H - 38, "Form GST REG-06", "Helvetica-Bold", 20, HexColor("#ffffff"), "center")
    text(c, W / 2, H - 56, "[See Rule 10(1)]", "Helvetica", 9, HexColor("#dbe4ff"), "center")
    text(c, W / 2, H - 76, "REGISTRATION CERTIFICATE", "Helvetica-Bold", 13, HexColor("#ffffff"), "center")
    text(c, 50, H - 122, "Registration Number :", "Helvetica", 10, GREY)
    text(c, 175, H - 122, "27AABCS1429E1Z8", "Courier-Bold", 14)
    rows = [
        ["1.", "Legal Name", "SHARMA FOODS PRIVATE LIMITED"],
        ["2.", "Trade Name, if any", "Sharma Foods"],
        ["3.", "Constitution of Business", "Private Limited Company"],
        ["4.", "Address of Principal Place of Business", "12 Mahatma Gandhi Marg, Navi Mumbai - 400703, Maharashtra"],
        ["5.", "Date of Liability", "04/08/2021"],
        ["6.", "Period of Validity", "From 04/08/2021   To Not Applicable"],
        ["7.", "Type of Registration", "Regular Taxpayer"],
    ]
    y = grid(c, 50, H - 140, [28, 214, W - 100 - 242], rows, row_h=36, header=False, size=9.2)
    text(c, 50, y - 24, "Details of Additional Places of Business", "Helvetica-Bold", 9.5)
    y = grid(c, 50, y - 32, [60, W - 100 - 60], [["S.No.", "Details"], ["-", "Nil"]], row_h=22, size=9)
    text(c, 50, y - 28, "Date of issue of Certificate : 06/08/2021", "Helvetica", 9.5)
    text(c, 50, y - 50, "The registration certificate is valid subject to compliance with the provisions of the Act and the Rules made thereunder.", "Helvetica-Oblique", 8, GREY)
    text(c, W - 60, y - 96, "Digitally signed", "Helvetica", 7.5, GREY, "right")
    text(c, W - 60, y - 107, "Proper Officer (Jurisdictional Office: Mumbai - CGST)", "Helvetica", 7.5, GREY, "right")
    signature(c, W - 190, y - 82, 3, width=100, height=12)
    text(c, 50, 60, "Note: This is a system generated certificate and does not require a physical signature (specimen format).", "Helvetica-Oblique", 7.5, GREY)
    specimen(c)
    c.save()


def coi(path: Path):
    c = new(path)
    c.setStrokeColor(HexColor("#7a5c1e"))
    c.setLineWidth(2.2)
    c.rect(30, 30, W - 60, H - 60, stroke=1, fill=0)
    c.setLineWidth(0.6)
    c.rect(36, 36, W - 72, H - 72, stroke=1, fill=0)
    text(c, W / 2, H - 82, "Ministry of Corporate Affairs", "Times-Bold", 15, HexColor("#3b2f12"), "center")
    text(c, W / 2, H - 100, "Office of the Registrar of Companies, Mumbai", "Times-Roman", 11, HexColor("#3b2f12"), "center")
    text(c, W / 2, H - 150, "Certificate of Incorporation", "Times-Bold", 23, HexColor("#3b2f12"), "center")
    text(c, W / 2, H - 170, "[Pursuant to sub-section (2) of section 7 of the Companies Act, 2013 and rule 8 of the Companies (Incorporation) Rules, 2014]", "Times-Italic", 8.5, GREY, "center")
    text(c, 70, H - 215, "Corporate Identity Number :", "Times-Roman", 11, GREY)
    text(c, 235, H - 215, "U56101MH2021PTC123456", "Courier-Bold", 14)
    body = [
        "I hereby certify that  SHARMA FOODS PRIVATE LIMITED  is this day incorporated",
        "under the Companies Act, 2013 (18 of 2013) and that the company is a Private Limited Company.",
        "",
        "The Permanent Account Number (PAN) of the company is AABCS1429E.",
        "",
        "The date of incorporation of the company is 14/08/2021.",
        "",
        "Registered Office :  12 MG Road, Mumbai - 400001, Maharashtra",
        "",
        "Given at Mumbai this Fourteenth day of August Two Thousand Twenty-One.",
    ]
    yy = H - 260
    for ln in body:
        if ln.startswith("I hereby"):
            a1, a2, a3 = "I hereby certify that  ", "SHARMA FOODS PRIVATE LIMITED", "  is this day incorporated"
            text(c, 70, yy, a1, "Times-Roman", 11.5)
            x2 = 70 + stringWidth(a1, "Times-Roman", 11.5)
            text(c, x2, yy, a2, "Times-Bold", 11.5)
            text(c, x2 + stringWidth(a2, "Times-Bold", 11.5), yy, a3, "Times-Roman", 11.5)
        else:
            text(c, 70, yy, ln, "Times-Roman", 11.5)
        yy -= 20
    text(c, W - 80, 150, "Registrar of Companies", "Times-Bold", 11, HexColor("#3b2f12"), "right")
    text(c, W - 80, 136, "Central Registration Centre, Mumbai", "Times-Roman", 9, GREY, "right")
    signature(c, W - 220, 178, 5, width=110, height=14)
    seal(c, 130, 160, 46, "REGISTRAR OF COMPANIES", "MUMBAI  MAHARASHTRA", rotate=8)
    text(c, 70, 78, "Mailing address as per record available in Registrar of Companies office:", "Times-Italic", 8.5, GREY)
    text(c, 70, 66, "SHARMA FOODS PRIVATE LIMITED, 12 MG Road, Mumbai - 400001, Maharashtra.", "Times-Italic", 8.5, GREY)
    specimen(c)
    c.save()


def board_resolution(path: Path, signatory: str = "Ravish Sahay", signatory_role: str = "Authorised Signatory", signatory_pan: str = "BQRPS4410K",
                     priya_din: str = "08492077"):
    c = new(path)
    y = letterhead(c, "SHARMA FOODS PRIVATE LIMITED", [
        "CIN: U56101MH2021PTC123456   |   PAN: AABCS1429E   |   GSTIN: 27AABCS1429E1Z8",
        "Registered Office: 12 MG Road, Mumbai - 400001, Maharashtra   |   accounts@sharmafoods.example   |   +91 22 5550 0142"])
    text(c, W / 2, y, "CERTIFIED TRUE COPY OF THE RESOLUTION PASSED BY THE BOARD OF DIRECTORS", "Times-Bold", 12, align="center")
    text(c, W / 2, y - 16, "at their meeting held on 02/09/2026 at 11:00 a.m. at the Registered Office of the Company", "Times-Roman", 10, GREY, "center")
    y -= 52
    text(c, 60, y, "Date of Resolution:", "Helvetica", 10, GREY)
    text(c, 170, y, "02/09/2026", "Helvetica-Bold", 10.5)
    y -= 34
    clauses = [
        ("1.", "RESOLVED THAT the Company be and is hereby authorised to open and operate a merchant account with Paytm Payment Gateway "
               "(One97 Communications Limited) for the purpose of accepting online payments from customers of the Company;"),
        ("2.", f"RESOLVED FURTHER THAT Mr. {signatory}, {signatory_role} of the Company, be and is hereby authorised to sign and execute "
               "all applications, agreements, declarations and documents, and to do all such acts, deeds and things as may be necessary or "
               "expedient for giving effect to this resolution;"),
        ("3.", "RESOLVED FURTHER THAT a certified copy of this resolution may be furnished to any person concerned as may be required."),
    ]
    for n, t in clauses:
        text(c, 60, y, n, "Times-Bold", 11)
        y = para(c, 82, y, t, "Times-Roman", 10.5, width=W - 82 - 60, leading=15) - 6
    y -= 14
    text(c, 60, y, "Specimen of the Authorised Signatory", "Helvetica-Bold", 10)
    y = grid(c, 60, y - 10, [150, 130, 120, W - 120 - 400], [
        ["Name", "Designation", "Specimen signature", "PAN"],
        [signatory, signatory_role, "", signatory_pan]], row_h=40, size=9)
    signature(c, 380, y + 20, 21, width=80, height=11)
    y -= 36
    text(c, 60, y, "Signed by the Directors:", "Helvetica", 10, GREY)
    y -= 56
    for i, (nm, din) in enumerate([("Anil Sharma", "DIN 08492019"), ("Priya Sharma", f"DIN {priya_din}")]):
        x0 = 60 + i * 240
        signature(c, x0, y + 24, 31 + i, width=90, height=13)
        c.setStrokeColor(LINE)
        c.line(x0 - 4, y + 8, x0 + 170, y + 8)
        text(c, x0, y - 6, nm + ", Director", "Helvetica-Bold", 10)
        text(c, x0, y - 19, din, "Helvetica", 8.5, GREY)
    text(c, 60, y - 52, "For Sharma Foods Private Limited", "Helvetica-Oblique", 9, GREY)
    text(c, 60, y - 64, "Place: Mumbai          Date: 02/09/2026", "Helvetica", 9, GREY)
    seal(c, W - 92, y - 30, 44, "SHARMA FOODS PRIVATE LIMITED", "MUMBAI  MAHARASHTRA", rotate=-10)
    stamp_box(c, W - 290, y - 78, 140, 34, "CERTIFIED\nTRUE COPY", rotate=5)
    specimen(c)
    c.save()


def bank_cheque(path: Path, holder: str = "Sharma Foods"):
    c = new(path)
    text(c, 50, H - 54, "Scanned copy of the cancelled cheque leaf", "Helvetica-Oblique", 9, GREY)
    x, y, w, h = 40, H - 360, W - 80, 270
    gradient(c, x, y, w, h, (0.93, 0.96, 0.99), (0.99, 0.97, 0.93))
    wave_pattern(c, x, y, w, h, (0.55, 0.65, 0.85), n=18, amp=4, alpha=0.25)
    c.setStrokeColor(HexColor("#6f7a99"))
    c.setLineWidth(1)
    c.rect(x, y, w, h, stroke=1, fill=0)
    c.setFillColor(HexColor("#c8102e"))
    c.rect(x + 16, y + h - 46, 22, 22, stroke=0, fill=1)                       # generic square mark, not a real logo
    c.setFillColor(HexColor("#ffffff"))
    c.rect(x + 22, y + h - 40, 10, 10, stroke=0, fill=1)
    text(c, x + 46, y + h - 36, "HDFC BANK", "Helvetica-Bold", 16, HexColor("#12306b"))
    text(c, x + 46, y + h - 48, "Fort Branch, Mumbai - 400001", "Helvetica", 7.5, GREY)
    text(c, x + w - 16, y + h - 34, "DATE", "Helvetica", 7.5, GREY, "right")
    for i in range(8):
        c.rect(x + w - 172 + i * 19, y + h - 56, 17, 16, stroke=1, fill=0)
    text(c, x + 16, y + h - 84, "PAY", "Helvetica-Bold", 10, HexColor("#12306b"))
    c.line(x + 46, y + h - 86, x + w - 150, y + h - 86)
    text(c, x + w - 140, y + h - 84, "OR BEARER", "Helvetica", 7.5, GREY)
    text(c, x + 16, y + h - 112, "RUPEES", "Helvetica-Bold", 10, HexColor("#12306b"))
    c.line(x + 64, y + h - 114, x + w - 150, y + h - 114)
    c.rect(x + w - 140, y + h - 130, 124, 26, stroke=1, fill=0)
    text(c, x + w - 134, y + h - 122, "Rs.", "Helvetica-Bold", 12)
    text(c, x + 16, y + 112, "A/c Name :", "Helvetica", 8, GREY)
    text(c, x + 76, y + 112, holder, "Helvetica-Bold", 13)
    text(c, x + 16, y + 92, "A/c No. :", "Helvetica", 8, GREY)
    text(c, x + 76, y + 92, "50200034928174", "Courier-Bold", 13)
    text(c, x + 16, y + 74, "IFSC :", "Helvetica", 8, GREY)
    text(c, x + 76, y + 74, "HDFC0000128", "Courier-Bold", 12)
    text(c, x + 16, y + 58, "Account Type :", "Helvetica", 8, GREY)
    text(c, x + 76, y + 58, "Current", "Helvetica-Bold", 10)
    text(c, x + w - 16, y + 100, "Authorised Signatory", "Helvetica", 7.5, GREY, "right")
    c.line(x + w - 190, y + 108, x + w - 16, y + 108)
    c.setStrokeColor(Color(0.1, 0.17, 0.55, alpha=0.8))
    c.setLineWidth(2)                                                           # crossing lines and CANCELLED, clear of the data
    c.line(x + 14, y + h - 14, x + 112, y + h - 14)
    stamp_box(c, x + 150, y + 136, 170, 36, "CANCELLED", rotate=-4, color=Color(0.1, 0.17, 0.55, alpha=0.75))
    c.setFillColor(HexColor("#222222"))
    c.setFont("Courier-Bold", 14)                                                # MICR band
    c.drawString(x + 22, y + 22, "c000128c  :400240002:  029246 c 31")
    c.rect(x, y + 12, w, 24, stroke=0, fill=0)
    c.setFont("Courier-Bold", 14)
    specimen(c)
    c.save()


def director_kyc(path: Path, name: str = "Anil Sharma", din: str | None = "08492019", last4: str = "4821", dob: str = "09/03/1978", relation: str = "",
                 address: str = "12 MG Road, Mumbai - 400001"):
    c = new(path)
    text(c, 50, H - 54, "Identity proof of the Director (masked copy, as submitted)" if din else "Identity proof (masked copy, as submitted)", "Helvetica-Oblique", 9, GREY)
    x, y, w, h = 60, H - 330, W - 120, 232
    c.setFillColor(HexColor("#fff6ec"))
    c.roundRect(x, y, w, h, 10, stroke=0, fill=1)
    c.setStrokeColor(HexColor("#d4a373"))
    c.roundRect(x, y, w, h, 10, stroke=1, fill=0)
    c.setFillColor(HexColor("#e07a1f"))
    c.rect(x, y + h - 36, w, 36, stroke=0, fill=1)
    text(c, x + 16, y + h - 24, "UNIQUE IDENTITY CARD (specimen layout)", "Helvetica-Bold", 11.5, HexColor("#ffffff"))
    c.setFillColor(HexColor("#e6e8ef"))
    c.rect(x + 18, y + 44, 92, 112, stroke=0, fill=1)                           # photo placeholder with a silhouette
    c.setFillColor(HexColor("#aeb3c4"))
    c.circle(x + 64, y + 118, 22, stroke=0, fill=1)
    c.ellipse(x + 30, y + 44, x + 98, y + 100, stroke=0, fill=1)
    text(c, x + 130, y + h - 66, "Name", "Helvetica", 8, GREY)
    text(c, x + 130, y + h - 84, name, "Helvetica-Bold", 16)
    text(c, x + 130, y + h - 108, "Date of Birth", "Helvetica", 8, GREY)
    text(c, x + 130, y + h - 123, dob, "Helvetica-Bold", 11)
    text(c, x + 250, y + h - 108, "Gender", "Helvetica", 8, GREY)
    text(c, x + 250, y + h - 123, "Male", "Helvetica-Bold", 11)
    text(c, x + 130, y + h - 146, "Address", "Helvetica", 8, GREY)
    text(c, x + 130, y + h - 160, address, "Helvetica-Bold", 10.5)
    text(c, x + 130, y + h - 174, "Maharashtra, India", "Helvetica", 9.5)
    text(c, x + w / 2, y + 22, f"XXXX XXXX {last4}", "Helvetica-Bold", 19, align="center")
    text(c, x + w / 2, y + 8, "Masked identification number (first 8 digits hidden)", "Helvetica", 7, GREY, "center")
    y2 = y - 48
    if din:
        text(c, 60, y2, "Director Identification Number (DIN) allotment", "Helvetica-Bold", 11)
        y2 = grid(c, 60, y2 - 10, [170, W - 120 - 170], [["Director name", name], ["DIN", din], ["Date of allotment", "21/06/2021"],
                                                           ["Status", "Approved"]], row_h=26, header=False, bold_first_col=True, size=9.5)
        text(c, 60, y2 - 22, "Extract of the master data of the director, as available with the Ministry (specimen).", "Helvetica-Oblique", 8, GREY)
    else:
        text(c, 60, y2, "Beneficial owner identification", "Helvetica-Bold", 11)
        y2 = grid(c, 60, y2 - 10, [170, W - 120 - 170], [["Name", name], ["Relationship", relation], ["Identity proof", "Masked identity card (above)"],
                                                           ["KYC status", "Submitted by the company"]], row_h=26, header=False, bold_first_col=True, size=9.5)
        text(c, 60, y2 - 22, "Submitted along with the beneficial-ownership declaration of the company (specimen).", "Helvetica-Oblique", 8, GREY)
    specimen(c)
    c.save()


def shareholding(path: Path):
    c = new(path)
    y = letterhead(c, "SHARMA FOODS PRIVATE LIMITED", [
        "CIN: U56101MH2021PTC123456   |   Registered Office: 12 MG Road, Mumbai - 400001, Maharashtra"])
    text(c, W / 2, y, "DECLARATION OF SHAREHOLDING AND BENEFICIAL OWNERSHIP", "Times-Bold", 13, align="center")
    text(c, W / 2, y - 16, "Sharma Foods Private Limited   |   as of 01/09/2026", "Times-Roman", 10.5, GREY, "center")
    y -= 52
    text(c, 60, y, "A.  Direct shareholders of the company", "Helvetica-Bold", 10.5)
    y = grid(c, 60, y - 10, [34, 190, 90, 90, 90], [
        ["S.No.", "Name of shareholder", "Type", "No. of shares", "% holding"],
        ["1", "Anil Sharma", "Individual", "4,000", "40%"],
        ["2", "Priya Sharma", "Individual", "3,000", "30%"],
        ["3", "Sharma Holdings LLP", "LLP", "3,000", "30%"],
        ["", "Total", "", "10,000", "100%"]], row_h=26, size=9.5)
    y -= 34
    text(c, 60, y, "B.  Partners of the corporate shareholder  Sharma Holdings LLP", "Helvetica-Bold", 10.5)
    y = grid(c, 60, y - 10, [34, 190, 180, 90], [
        ["S.No.", "Name of partner", "Entity", "% of the LLP"],
        ["1", "Rakesh Sharma", "Sharma Holdings LLP", "60%"],
        ["2", "Meera Sharma", "Sharma Holdings LLP", "40%"]], row_h=26, size=9.5)
    y -= 40
    for ln in ["I hereby declare that the above particulars of shareholding and of the partners of the corporate shareholder are true and",
               "correct to the best of my knowledge and belief, and that I shall inform the bank of any change without delay."]:
        text(c, 60, y, ln, "Times-Roman", 10)
        y -= 15
    y -= 44
    signature(c, 60, y + 20, 41, width=96, height=14)
    c.setStrokeColor(LINE)
    c.line(56, y + 6, 240, y + 6)
    text(c, 60, y - 8, "Anil Sharma, Director", "Helvetica-Bold", 10)
    text(c, 60, y - 21, "Date: 01/09/2026     Place: Mumbai", "Helvetica", 8.5, GREY)
    seal(c, W - 130, y + 14, 44, "SHARMA FOODS PRIVATE LIMITED", "MUMBAI  MAHARASHTRA", rotate=9)
    specimen(c)
    c.save()


def fssai(path: Path):
    c = new(path)
    c.setFillColor(HexColor("#1a6b3a"))
    c.rect(0, H - 100, W, 100, stroke=0, fill=1)
    c.setFillColor(HexColor("#ffffff"))
    c.setStrokeColor(HexColor("#ffffff"))
    c.circle(76, H - 50, 24, stroke=1, fill=0)
    text(c, 76, H - 55, "FSS", "Helvetica-Bold", 14, HexColor("#ffffff"), "center")
    text(c, 120, H - 40, "FOOD SAFETY AND STANDARDS ACT, 2006", "Helvetica-Bold", 14, HexColor("#ffffff"))
    text(c, 120, H - 58, "Licence for Food Business Operator (specimen format)", "Helvetica", 10, HexColor("#d7f3e1"))
    text(c, 120, H - 76, "Form C   |   Licence under Regulation 2.1.2 (specimen)", "Helvetica", 8.5, HexColor("#d7f3e1"))
    text(c, 50, H - 134, "Licence No. :", "Helvetica", 10, GREY)
    text(c, 130, H - 134, "11521999000123", "Courier-Bold", 18)
    rows = [
        ["Name of the Food Business Operator", "SHARMA FOODS PRIVATE LIMITED"],
        ["Address of the Premises", "12 Mahatma Gandhi Marg, Navi Mumbai - 400703"],
        ["Licence Type", "State Licence"],
        ["Kind of Business", "Manufacturer"],
        ["Category", "Spices, snacks and ready-to-eat food products"],
        ["Date of Issue / Valid From", "10/10/2025"],
        ["Valid Until", "09/10/2030"],
    ]
    y = grid(c, 50, H - 150, [190, W - 100 - 190], rows, row_h=34, header=False, bold_first_col=True, size=9.5)
    text(c, 50, y - 26, "This licence is subject to the conditions printed overleaf and to renewal before the date of expiry.", "Helvetica-Oblique", 8, GREY)
    signature(c, W - 190, y - 70, 7, width=100, height=12)
    text(c, W - 60, y - 98, "Designated Officer", "Helvetica-Bold", 9, align="right")
    text(c, W - 60, y - 110, "Food Safety Department, Maharashtra (specimen)", "Helvetica", 8, GREY, "right")
    seal(c, 110, y - 80, 40, "FOOD SAFETY OFFICER", "MAHARASHTRA", rotate=-7)
    specimen(c)
    c.save()


def electricity_bill(path: Path):
    c = new(path)
    c.setFillColor(HexColor("#0a5c8f"))
    c.rect(0, H - 86, W, 86, stroke=0, fill=1)
    text(c, 50, H - 40, "WESTERN POWER DISTRIBUTION COMPANY LIMITED", "Helvetica-Bold", 15, HexColor("#ffffff"))
    text(c, 50, H - 58, "Electricity Bill - Commercial (LT-II) consumer", "Helvetica", 10, HexColor("#cfe8f7"))
    text(c, 50, H - 74, "Customer care 1912   |   fictional utility for a software demonstration", "Helvetica", 8, HexColor("#cfe8f7"))
    text(c, W - 50, H - 44, "BILL", "Helvetica-Bold", 22, HexColor("#ffffff"), "right")
    rows = [
        ["Consumer Name", "SHARMA FOODS PRIVATE LIMITED"],
        ["Consumer Number", "170240055310"],
        ["Service Address", "12 Mahatma Gandhi Marg, Navi Mumbai - 400703, Maharashtra"],
        ["Bill Date", "05/09/2026"],
        ["Due Date", "20/09/2026"],
        ["Billing Period", "05/08/2026 to 04/09/2026"],
    ]
    y = grid(c, 50, H - 110, [150, W - 100 - 150], rows, row_h=30, header=False, bold_first_col=True, size=9.5)
    y -= 26
    text(c, 50, y, "Charges for the month", "Helvetica-Bold", 10.5)
    y = grid(c, 50, y - 8, [250, 90, 80, W - 100 - 420], [
        ["Description", "Units (kWh)", "Rate", "Amount (Rs.)"],
        ["Energy charges", "1,842", "9.25", "17,038.50"],
        ["Fixed / demand charges", "-", "-", "2,400.00"],
        ["Electricity duty and taxes", "-", "-", "1,610.30"],
        ["Total amount payable", "", "", "21,048.80"]], row_h=26, size=9.5)
    text(c, 50, y - 28, "Pay online or at any authorised centre before the due date to avoid a delayed payment charge.", "Helvetica-Oblique", 8, GREY)
    c.setFillColor(HexColor("#eef0f7"))
    c.rect(50, 70, W - 100, 46, stroke=0, fill=1)
    text(c, 60, 98, "Meter reading: previous 48,201   current 50,043   consumption 1,842 kWh", "Helvetica", 9)
    text(c, 60, 82, "Supply type: Three phase   |   Sanctioned load: 30 kW", "Helvetica", 9, GREY)
    specimen(c)
    c.save()


def bharat_business_proof(path: Path):
    """Bharat Agri Logistics LLP (KYB-20815): a Shops and Establishments registration with the municipal trade licence, the 'Business Registration / Municipal Proof' upload."""
    c = new(path)
    c.setFillColor(HexColor("#7a3b10"))
    c.rect(0, H - 100, W, 100, stroke=0, fill=1)
    c.setFillColor(HexColor("#ffffff"))
    c.setStrokeColor(HexColor("#ffffff"))
    c.circle(76, H - 50, 24, stroke=1, fill=0)
    text(c, 76, H - 55, "VMC", "Helvetica-Bold", 13, HexColor("#ffffff"), "center")
    text(c, 120, H - 40, "VADODARA MUNICIPAL CORPORATION (specimen)", "Helvetica-Bold", 14, HexColor("#ffffff"))
    text(c, 120, H - 58, "Registration Certificate under the Shops and Establishments Act and Trade Licence", "Helvetica", 9.5, HexColor("#f5dcc4"))
    text(c, 120, H - 76, "Form-B   |   Certificate of Registration of an Establishment (specimen format)", "Helvetica", 8.5, HexColor("#f5dcc4"))
    text(c, 50, H - 134, "Registration No. :", "Helvetica", 10, GREY)
    text(c, 150, H - 134, "VMC/SE/2020/048213", "Courier-Bold", 15)
    text(c, W - 50, H - 134, "Trade Licence No. : TL/VAD/2020/7714", "Helvetica", 9, GREY, "right")
    rows = [
        ["1.", "Name of the Establishment", "BHARAT AGRI LOGISTICS LLP"],
        ["2.", "Nature of Business", "Agricultural produce transport and warehousing (logistics)"],
        ["3.", "Address of the Establishment", "Plot 14, GIDC Estate, Vadodara - 390010, Gujarat"],
        ["4.", "Name of the Employer / Partner", "Kiran Patel (Designated Partner)"],
        ["5.", "Constitution", "Limited Liability Partnership"],
        ["6.", "PAN / GSTIN of the Establishment", "AAJFB5521K  /  24AAJFB5521K1Z2"],
        ["7.", "Date of Registration", "11/02/2020"],
        ["8.", "Valid Up To", "31/03/2027 (renewable annually)"],
    ]
    y = grid(c, 50, H - 150, [28, 190, W - 100 - 218], rows, row_h=34, header=False, size=9.2)
    text(c, 50, y - 26, "The establishment is registered, and is permitted to carry on the trade above at the premises named, subject to the conditions of the Act.", "Helvetica-Oblique", 8, GREY)
    text(c, 50, y - 40, "Display this certificate at a conspicuous place in the establishment.", "Helvetica-Oblique", 8, GREY)
    signature(c, W - 190, y - 86, 17, width=100, height=12)
    text(c, W - 60, y - 112, "Inspector, Shops and Establishments", "Helvetica-Bold", 9, align="right")
    text(c, W - 60, y - 124, "Vadodara Municipal Corporation (specimen)", "Helvetica", 8, GREY, "right")
    seal(c, 118, y - 92, 42, "MUNICIPAL CORPORATION", "VADODARA  GUJARAT", rotate=-8, mark="VMC")
    specimen(c)
    c.save()


PACK = {
    "01_Company_PAN.pdf": pan,
    "02_GST_Certificate.pdf": gst,
    "03_Certificate_of_Incorporation.pdf": coi,
    "04_Board_Resolution.pdf": board_resolution,
    "05_Cancelled_Cheque.pdf": bank_cheque,
    "06_Director_KYC_Anil_Sharma.pdf": director_kyc,
    "07_Shareholding_Declaration.pdf": shareholding,
    "08_FSSAI_Licence.pdf": fssai,
    "09_Electricity_Bill.pdf": electricity_bill,
}


def _kyc(name, din, last4, dob, relation="", address="12 MG Road, Mumbai - 400001"):
    return lambda path: director_kyc(path, name=name, din=din, last4=last4, dob=dob, relation=relation, address=address)


FIX_PACK = {
    "F1_Cancelled_Cheque_CORRECTED.pdf": lambda path: bank_cheque(path, holder="SHARMA FOODS PRIVATE LIMITED"),
    "F2_Director_KYC_Priya_Sharma.pdf": _kyc("Priya Sharma", "08492077", "7733", "22/11/1981"),
    "F3_Owner_KYC_Rakesh_Sharma.pdf": _kyc("Rakesh Sharma", None, "5590", "03/05/1975", "Partner (60%), Sharma Holdings LLP (30% shareholder)", "44 Linking Road, Mumbai - 400050"),
    "F4_Owner_KYC_Meera_Sharma.pdf": _kyc("Meera Sharma", None, "3318", "17/09/1979", "Partner (40%), Sharma Holdings LLP (30% shareholder)", "44 Linking Road, Mumbai - 400050"),
}


def generate_fixes(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, fn in FIX_PACK.items():
        p = out_dir / name
        fn(p)
        paths.append(p)
    return paths


# The all-correct set: every document consistent with the others and with the (mock) registry. No planted problem.
#   cheque in the full legal name; the board resolution authorises a current director; every owner above 10% has an identity proof.
CORRECT_PACK = {
    "01_Company_PAN.pdf": pan,
    "02_GST_Certificate.pdf": gst,
    "03_Certificate_of_Incorporation.pdf": coi,
    "04_Board_Resolution.pdf": lambda path: board_resolution(path, signatory="Anil Sharma", signatory_role="Director and Authorised Signatory",
                                                             signatory_pan="AKXPS8821M", priya_din="08492020"),
    "05_Cancelled_Cheque.pdf": lambda path: bank_cheque(path, holder="SHARMA FOODS PRIVATE LIMITED"),
    "06_Director_KYC_Anil_Sharma.pdf": director_kyc,
    "07_Director_KYC_Priya_Sharma.pdf": lambda path: director_kyc(path, name="Priya Sharma", din="08492020", last4="7733", dob="22/11/1981"),
    "08_Owner_KYC_Rakesh_Sharma.pdf": lambda path: director_kyc(path, name="Rakesh Sharma", din=None, last4="5590", dob="03/05/1975",
                                                                relation="Partner (60%), Sharma Holdings LLP (30% shareholder)", address="44 Linking Road, Mumbai - 400050"),
    "09_Owner_KYC_Meera_Sharma.pdf": lambda path: director_kyc(path, name="Meera Sharma", din=None, last4="3318", dob="17/09/1979",
                                                               relation="Partner (40%), Sharma Holdings LLP (30% shareholder)", address="44 Linking Road, Mumbai - 400050"),
    "10_Shareholding_Declaration.pdf": shareholding,
    "11_FSSAI_Licence.pdf": fssai,
    "12_Electricity_Bill.pdf": electricity_bill,
}


def generate_correct(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, fn in CORRECT_PACK.items():
        p = out_dir / name
        fn(p)
        paths.append(p)
    return paths


def generate_bharat(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "Bharat_Agri_Business_Registration_Municipal_Proof.pdf"
    bharat_business_proof(p)
    return [p]


def generate(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, fn in PACK.items():
        p = out_dir / name
        fn(p)
        paths.append(p)
    return paths


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "demo_pack"
    for p in generate(target) + generate_fixes(target / "fixes") + generate_correct(target.parent / "demo_pack_correct") + generate_bharat(target.parent / "demo_pack_bharat"):
        print("wrote", p)
