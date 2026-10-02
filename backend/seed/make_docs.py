"""Generates SYNTHETIC specimen documents for the Sharma Foods hero case (reportlab).

Every page carries a diagonal "SPECIMEN - SYNTHETIC DEMO DATA" watermark, no government emblems or logos.
The documents contain the four planted issues:
  1. cheque account name "Sharma Foods" != legal name "Sharma Foods Private Limited"
  2. board resolution signatory (Ravish Sahay) is not a current director (MCA: Anil Sharma, Priya Sharma)
  3. hidden beneficial owner: Sharma Holdings LLP owns 30%, Rakesh Sharma holds 60% of it -> 18% effective
  4. address drift: GST principal place says Navi Mumbai, application says Mumbai
Output is byte-for-byte deterministic (reportlab invariant mode), so the Sarvam demo cache, which is keyed by
SHA-256, matches regenerated files on any machine.
Usage: python -m seed.make_docs [output_dir]
"""
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

W, H = A4
LEFT = 50


def _page(c: canvas.Canvas, title: str, subtitle: str = "") -> float:
    c.saveState()
    c.setFillColorRGB(0.85, 0.85, 0.88)
    c.setFont("Helvetica-Bold", 38)
    c.translate(W / 2, H / 2)
    c.rotate(35)
    c.drawCentredString(0, 0, "SPECIMEN - SYNTHETIC DEMO DATA")
    c.restoreState()
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(W / 2, H - 70, title)
    if subtitle:
        c.setFont("Helvetica", 9)
        c.drawCentredString(W / 2, H - 86, subtitle)
    c.line(LEFT, H - 98, W - LEFT, H - 98)
    return H - 130


def _rows(c: canvas.Canvas, y: float, rows: list[tuple[str, str]], label_w: int = 190, gap: int = 30) -> float:
    for label, value in rows:
        c.setFont("Helvetica", 10)
        c.setFillColorRGB(0.35, 0.35, 0.4)
        c.drawString(LEFT, y, label)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(LEFT + label_w, y, value)
        y -= gap
    return y


def pan(path: Path):
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    y = _page(c, "PERMANENT ACCOUNT NUMBER CARD", "Specimen card - income tax department format (synthetic)")
    _rows(c, y, [("Permanent Account Number", "AABCS1429E"),
                 ("Name", "SHARMA FOODS PRIVATE LIMITED"),
                 ("Date of Incorporation/Formation", "14/08/2021")])
    c.save()


def gst(path: Path):
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    y = _page(c, "FORM GST REG-06 - REGISTRATION CERTIFICATE", "Registration under Goods and Services Tax Act, 2017 (synthetic specimen)")
    _rows(c, y, [("Registration Number", "27AABCS1429E1Z8"),
                 ("Legal Name", "SHARMA FOODS PRIVATE LIMITED"),
                 ("Trade Name", "Sharma Foods"),
                 ("Constitution of Business", "Private Limited Company"),
                 ("Address of Principal Place of Business", ""),
                 ("", "12 Mahatma Gandhi Marg, Navi Mumbai - 400703, Maharashtra"),
                 ("Date of Liability", "04/08/2021"),
                 ("Type of Registration", "Regular Taxpayer"),
                 ("Period of Validity", "From 04/08/2021 To Not Applicable")], label_w=230)
    c.save()


def coi(path: Path):
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    y = _page(c, "CERTIFICATE OF INCORPORATION", "Companies Act, 2013 (synthetic specimen)")
    _rows(c, y, [("Corporate Identity Number", "U56101MH2021PTC123456"),
                 ("Company Name", "SHARMA FOODS PRIVATE LIMITED"),
                 ("Date of Incorporation", "14/08/2021"),
                 ("Type of Company", "Private Limited Company"),
                 ("Registered Office", "12 MG Road, Mumbai - 400001, Maharashtra"),
                 ("Registrar", "Registrar of Companies, Mumbai")])
    c.save()


def board_resolution(path: Path):
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    y = _page(c, "CERTIFIED TRUE COPY OF BOARD RESOLUTION", "Sharma Foods Private Limited | CIN U56101MH2021PTC123456")
    y = _rows(c, y, [("Date of Resolution", "02/09/2026"), ("Company", "SHARMA FOODS PRIVATE LIMITED")])
    c.setFont("Helvetica", 10)
    for line in [
        "RESOLVED THAT the Company be and is hereby authorised to open and operate a merchant account",
        "with Paytm Payment Gateway (One97 Communications Limited) for accepting online payments;",
        "",
        "RESOLVED FURTHER THAT Mr. Ravish Sahay, Authorised Signatory, be and is hereby authorised to",
        "sign all applications, agreements and documents, and to do all acts required in this regard.",
    ]:
        c.drawString(LEFT, y, line)
        y -= 16
    y -= 20
    _rows(c, y, [("Authorised Signatory", "Ravish Sahay"), ("Designation", "Authorised Signatory"),
                 ("Signed by Directors", "Anil Sharma, Priya Sharma")])
    c.save()


def bank_cheque(path: Path):
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    y = _page(c, "CANCELLED CHEQUE", "HDFC Bank Ltd - specimen cheque leaf (synthetic)")
    y = _rows(c, y, [("Account Holder (pre-printed)", "Sharma Foods"),
                 ("Account Number", "50200034928174"),
                 ("IFSC", "HDFC0000128"),
                 ("Bank", "HDFC Bank"),
                 ("Branch", "Fort, Mumbai"),
                 ("Account Type", "Current")], label_w=210)
    c.setFont("Helvetica-Bold", 28)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(LEFT + 120, y - 30, "CANCELLED")   # below the data rows; never over the numbers
    c.save()


def director_kyc(path: Path, name: str = "Anil Sharma", din: str = "08492019", last4: str = "4821"):
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    y = _page(c, "IDENTITY PROOF (MASKED)", "Masked Aadhaar format - specimen (synthetic)")
    _rows(c, y, [("Name", name), ("ID Type", "Aadhaar (masked)"), ("Aadhaar", f"XXXX XXXX {last4}"),
                 ("DIN", din), ("Date of Birth", "09/03/1978"),
                 ("Address", "12 MG Road, Mumbai - 400001")])
    c.save()


def shareholding(path: Path):
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    y = _page(c, "SHAREHOLDING & BENEFICIAL OWNER DECLARATION", "Sharma Foods Private Limited | as of 01/09/2026 (synthetic)")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(LEFT, y, "Direct shareholders")
    y -= 20
    for name, kind, pct in [("Anil Sharma", "individual", "40"), ("Priya Sharma", "individual", "30"),
                            ("Sharma Holdings LLP", "llp", "30")]:
        c.setFont("Helvetica", 10)
        c.drawString(LEFT, y, name)
        c.drawString(LEFT + 220, y, kind)
        c.drawString(LEFT + 330, y, f"{pct}%")
        y -= 20
    y -= 20
    c.setFont("Helvetica-Bold", 10)
    c.drawString(LEFT, y, "Partners of Sharma Holdings LLP")
    y -= 20
    for name, pct in [("Rakesh Sharma", "60"), ("Meera Sharma", "40")]:
        c.setFont("Helvetica", 10)
        c.drawString(LEFT, y, name)
        c.drawString(LEFT + 330, y, f"{pct}%")
        y -= 20
    c.save()


def fssai(path: Path):
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    y = _page(c, "FSSAI LICENCE", "Food Safety and Standards Act, 2006 (synthetic specimen)")
    _rows(c, y, [("Licence Number", "11521999000123"),
                 ("Business Name", "SHARMA FOODS PRIVATE LIMITED"),
                 ("Premises", "12 Mahatma Gandhi Marg, Navi Mumbai - 400703"),
                 ("Licence Type", "State Licence"), ("Kind of Business", "Manufacturer"),
                 ("Valid From", "10/10/2025"), ("Valid Until", "09/10/2030")])
    c.save()


HERO_FILES = {
    "Company_PAN.pdf": pan,
    "GST_Certificate.pdf": gst,
    "Certificate_of_Incorporation.pdf": coi,
    "Board_Resolution.pdf": board_resolution,
    "Cancelled_Cheque.pdf": bank_cheque,
    "Director_KYC_Anil_Sharma.pdf": director_kyc,
    "Shareholding_Declaration.pdf": shareholding,
    "FSSAI_Licence.pdf": fssai,
}


def generate(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, fn in HERO_FILES.items():
        p = out_dir / name
        fn(p)
        paths.append(p)
    return paths


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "sharma_foods"
    for p in generate(target):
        print("wrote", p)
