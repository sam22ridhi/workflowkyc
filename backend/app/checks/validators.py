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


# ---------------------------------------------------------------- per-document format checks (all doc types)
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
CIN_RE = re.compile(r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
MASKED_AADHAAR_RE = re.compile(r"^(X{4}|\*{4})[ -]?(X{4}|\*{4})[ -]?[0-9]{4}$", re.I)


def _chk(id_: str, label: str, ok: bool, detail: str, warn: bool = False) -> dict:
    return {"id": id_, "label": label, "status": "pass" if ok else ("warn" if warn else "fail"), "detail": detail}


def _clean(v) -> str:
    return re.sub(r"\s+", "", _get(v)).upper()


def check_document(doc_type: str, fields: dict, case) -> list[dict]:
    """Single-document rule checks. `fields` is {key: plain value}; `case` supplies declared entity data."""
    if doc_type == "pan":
        return check_pan(fields, getattr(case, "entity_type", None), getattr(case, "legal_name", None))
    out: list[dict] = []
    if doc_type == "gst":
        g = _clean(fields.get("gstin"))
        out.append(_chk("gstin_format", "GSTIN format (15 chars)", bool(GSTIN_RE.match(g)), g or "GSTIN not found"))
        if GSTIN_RE.match(g) and PAN_RE.match(_clean(getattr(case, "pan", ""))):
            out.append(_chk("gstin_embeds_pan", "GSTIN characters 3-12 equal company PAN", g[2:12] == _clean(case.pan),
                            f"GSTIN has {g[2:12]}, case PAN is {_clean(case.pan)}"))
    elif doc_type == "coi":
        cin = _clean(fields.get("cin"))
        out.append(_chk("cin_format", "CIN format (21 chars)", bool(CIN_RE.match(cin)), cin or "CIN not found"))
    elif doc_type == "bank_cheque":
        ifsc, acct = _clean(fields.get("ifsc")), re.sub(r"\D", "", _get(fields.get("account_number")))
        out.append(_chk("ifsc_format", "IFSC format (AAAA0XXXXXX)", bool(IFSC_RE.match(ifsc)), ifsc or "IFSC not found"))
        out.append(_chk("account_number_format", "Account number 9-18 digits", 9 <= len(acct) <= 18, acct or "not found"))
        at = _get(fields.get("account_type")).lower()
        if at:
            out.append(_chk("account_type_current", "Current account (corporate entities)", "current" in at, at))
    elif doc_type == "fssai":
        n = re.sub(r"\D", "", _get(fields.get("licence_number")))
        out.append(_chk("fssai_format", "FSSAI number is 14 digits", len(n) == 14, n or "not found"))
    elif doc_type == "director_kyc":
        a = _get(fields.get("aadhaar_masked"))
        if a:
            out.append(_chk("aadhaar_masked", "Aadhaar is masked (last 4 digits only)", bool(MASKED_AADHAAR_RE.match(a)), a))
    elif doc_type == "board_resolution":
        out.append(_chk("signatory_present", "Authorised signatory named",
                        bool(_get(fields.get("authorised_signatory_name"))), _get(fields.get("authorised_signatory_name")) or "none"))
    elif doc_type == "shareholding":
        total = 0.0
        for r in fields.get("shareholders") or []:
            try:
                total += float(str(r.get("percentage", "0")).replace("%", ""))
            except ValueError:
                pass
        out.append(_chk("shareholding_total", "Direct shareholding adds up to 100%", abs(total - 100) < 0.5, f"total {total:g}%", warn=True))
    return out


# ---------------------------------------------------------------- name comparison (CRM conflicts + cross-checks)
_ABBREV = {"PVT": "PRIVATE", "LTD": "LIMITED"}


def _strict_name(name: str) -> str:
    n = re.sub(r"[^A-Z0-9 ]", " ", (name or "").upper())
    return " ".join(_ABBREV.get(w, w) for w in n.split())


def name_match(a: str, b: str) -> str:
    """'same' (case/punctuation/Pvt-vs-Private only) | 'suffix' (equal once PRIVATE/LIMITED/LLP are dropped,
    e.g. 'Sharma Foods' vs 'Sharma Foods Private Limited') | 'different'."""
    if not _get(a) or not _get(b):
        return "different"
    if _strict_name(a) == _strict_name(b):
        return "same"
    return "suffix" if normalise_name(a) == normalise_name(b) else "different"
