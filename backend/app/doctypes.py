"""Document types, upload slots (as used by the merchant UI) and the required-document checklist."""
import re

DOC_TYPES: dict[str, str] = {
    "pan": "Company PAN",
    "gst": "GST Certificate (REG-06)",
    "coi": "Certificate of Incorporation",
    "board_resolution": "Board Resolution",
    "bank_cheque": "Cancelled Cheque / Bank Letter",
    "director_kyc": "Director KYC",
    "shareholding": "Shareholding / Beneficial Owner Declaration",
    "fssai": "FSSAI Licence",
    "electricity_bill": "Electricity Bill (address proof)",
    "unknown": "Unclassified document",
}

# Slots the merchant UI uploads into (MerchantUploadScreen.documentChecklist ids).
# A slot may hold several types, so the type is refined from a per-file hint, the filename, or classification.
SLOT_DEFAULT_TYPE: dict[str, str] = {
    "bank_details": "bank_cheque",
    "signatory_kyc": "director_kyc",
    "tax_gst": "unknown",
    "business_proof": "unknown",
}

# (regex on filename, type) - first match wins. Cheap first-pass; the KAM can correct a wrong guess.
FILENAME_HINTS: list[tuple[str, str]] = [
    (r"gst|reg[-_ ]?06", "gst"),
    (r"\bpan\b|pan[_-]|_pan", "pan"),
    (r"coi|incorporation|certificate[_ -]of[_ -]inc", "coi"),
    (r"board|resolution|\bbr\b", "board_resolution"),
    (r"cheque|check|bank|passbook|ifsc", "bank_cheque"),
    (r"kyc|aadhaar|aadhar|passport|voter|driving|director", "director_kyc"),
    (r"shareholding|share[_ -]?holder|beneficial|ubo|mgt", "shareholding"),
    (r"fssai|food[_ -]?licen", "fssai"),
    (r"electricity|electric[_ -]?bill|power[_ -]?bill|discom|msedcl|bses|bescom|tneb", "electricity_bill"),
]

# Required documents per entity type (cross-check #9) and per industry (#10).
REQUIRED_DOCS: dict[str, list[str]] = {
    "private_limited": ["pan", "gst", "coi", "board_resolution", "bank_cheque", "director_kyc", "shareholding"],
    "public_limited": ["pan", "gst", "coi", "board_resolution", "bank_cheque", "director_kyc", "shareholding"],
    "llp": ["pan", "gst", "coi", "board_resolution", "bank_cheque", "director_kyc", "shareholding"],
    "partnership": ["pan", "gst", "bank_cheque", "director_kyc"],
    "proprietorship": ["pan", "gst", "bank_cheque", "director_kyc"],
}
INDUSTRY_LICENCE: dict[str, str] = {"food": "fssai"}

ENTITY_LABELS = {
    "private_limited": "Private Limited",
    "public_limited": "Public Limited",
    "llp": "LLP",
    "partnership": "Partnership",
    "proprietorship": "Proprietorship",
}


def guess_doc_type(filename: str, slot: str | None = None, hint: str | None = None) -> str:
    """Hint from the client wins, then the filename, then the slot default."""
    if hint and hint in DOC_TYPES:
        return hint
    name = (filename or "").lower()
    for pattern, doc_type in FILENAME_HINTS:
        if re.search(pattern, name):
            return doc_type
    return SLOT_DEFAULT_TYPE.get(slot or "", "unknown")


def required_for(entity_type: str, industry: str | None) -> list[str]:
    required = list(REQUIRED_DOCS.get(entity_type, REQUIRED_DOCS["private_limited"]))
    licence = INDUSTRY_LICENCE.get((industry or "").lower())
    if licence and licence not in required:
        required.append(licence)
    return required
