"""Deterministic checks. The model READS the document; this code CHECKS it.

No LLM here: every rule is plain Python so results are repeatable and explainable.
"""
import re
from datetime import datetime

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")

# 4th character of a PAN = type of holder
PAN_HOLDER_TYPES = {
    "P": "Individual",
    "C": "Company",
    "F": "Firm / LLP",
    "T": "Trust",
    "H": "HUF",
    "A": "Association of Persons",
    "B": "Body of Individuals",
    "G": "Government",
    "J": "Artificial Juridical Person",
    "L": "Local Authority",
}

# Which 4th character we expect for each entity type the merchant declared
EXPECTED_4TH_CHAR = {
    "private_limited": "C",
    "public_limited": "C",
    "opc": "C",
    "section_8": "C",
    "llp": "F",
    "partnership": "F",
    "trust": "T",
    "huf": "H",
    "society": "A",  # societies are usually AOP; confirm per case
}

LEGAL_SUFFIXES = r"\b(PRIVATE|PVT|LIMITED|LTD|LLP|THE)\b\.?"


def normalise_name(name: str) -> str:
    n = (name or "").upper()
    n = re.sub(LEGAL_SUFFIXES, " ", n)
    n = re.sub(r"[^A-Z0-9 ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _get(value):
    return (value or "").strip() if isinstance(value, str) else ""


def check_pan(fields: dict, declared_entity_type: str | None = None,
              declared_name: str | None = None) -> list[dict]:
    """Return a list of checks: {id, label, status: pass|fail|warn|skip, detail}."""
    checks = []
    pan = _get(fields.get("pan_number")).upper().replace(" ", "")
    name = _get(fields.get("holder_name"))
    date = _get(fields.get("date"))

    # 1. Format
    fmt_ok = bool(PAN_RE.match(pan))
    checks.append({"id": "pan_format", "label": "PAN format (AAAAA9999A)",
                   "status": "pass" if fmt_ok else "fail",
                   "detail": pan or "PAN not found on document"})
    if not fmt_ok:
        return checks

    # 2. Holder type from 4th character
    fourth = pan[3]
    holder = PAN_HOLDER_TYPES.get(fourth, "Unknown")
    if declared_entity_type:
        expected = EXPECTED_4TH_CHAR.get(declared_entity_type)
        status = "skip" if not expected else ("pass" if fourth == expected else "fail")
        detail = f"4th char '{fourth}' = {holder}; declared '{declared_entity_type}' expects '{expected}'"
    else:
        status, detail = "skip", f"4th char '{fourth}' = {holder} (no declared entity type to compare)"
    checks.append({"id": "pan_holder_type", "label": "PAN holder type matches entity type",
                   "status": status, "detail": detail})

    # 3. 5th character is usually the first letter of the entity name (surname for individuals)
    if name and fourth != "P":
        first = normalise_name(name)[:1]
        checks.append({"id": "pan_5th_char", "label": "5th char matches first letter of name (soft check)",
                       "status": "pass" if first == pan[4] else "warn",
                       "detail": f"5th char '{pan[4]}', name starts with '{first}'"})

    # 4. Date is a real date
    try:
        datetime.strptime(date, "%d/%m/%Y")
        checks.append({"id": "pan_date", "label": "Date readable (DD/MM/YYYY)", "status": "pass", "detail": date})
    except ValueError:
        checks.append({"id": "pan_date", "label": "Date readable (DD/MM/YYYY)", "status": "warn",
                       "detail": date or "No date found"})

    # 5. Name on PAN vs name the merchant typed in Basic details
    if declared_name:
        same = normalise_name(declared_name) == normalise_name(name)
        checks.append({"id": "pan_name_match", "label": "Name matches declared legal name",
                       "status": "pass" if same else "fail",
                       "detail": f"PAN: '{name}' vs declared: '{declared_name}'"})
    return checks


def summarise(checks: list[dict]) -> str:
    if any(c["status"] == "fail" for c in checks):
        return "needs_attention"
    if any(c["status"] == "warn" for c in checks):
        return "review"
    return "verified"
