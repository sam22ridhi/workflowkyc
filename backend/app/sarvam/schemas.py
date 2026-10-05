"""Extraction schemas sent to Sarvam Document Intelligence (/doc-ai/v1/job/extract).

Sarvam rules: root is type "object" with non-empty "properties"; every field has a "type" and a non-empty
"description"; max nesting depth 4 (we stay at 3: root -> array -> item fields).
"""


def _s(description: str) -> dict:
    return {"type": "string", "description": description}


def _obj(properties: dict, description: str = "Extracted fields") -> dict:
    return {"type": "object", "description": description, "properties": properties}


def _arr(description: str, item_props: dict, item_desc: str) -> dict:
    return {"type": "array", "description": description, "items": _obj(item_props, item_desc)}


PAN_SCHEMA = _obj({
    "pan_number": _s("The 10-character Permanent Account Number printed on the card, e.g. AABCS1429E"),
    "holder_name": _s("Name of the PAN holder exactly as printed (person or entity/company name)"),
    "father_name": _s("Father's name, printed only on PAN cards of individuals. Empty if not present"),
    "date": _s("Date of birth (individual) or date of incorporation/formation (entity), as printed, in DD/MM/YYYY"),
    "date_label": _s("The label printed next to the date, e.g. 'Date of Birth' or 'Date of Incorporation/Formation'"),
})

GST_SCHEMA = _obj({
    "gstin": _s("The 15-character GST Identification Number / Registration Number, e.g. 27AABCS1429E1Z8"),
    "legal_name": _s("Legal name of the business exactly as printed"),
    "trade_name": _s("Trade name of the business, if printed"),
    "constitution_of_business": _s("Constitution of business, e.g. Private Limited Company, Partnership"),
    "principal_place_address": _s("Full address of the principal place of business exactly as printed, including city and PIN"),
    "date_of_liability": _s("Date of liability to register, as printed, DD/MM/YYYY"),
    "registration_type": _s("Type of registration, e.g. Regular Taxpayer"),
    "validity_from": _s("Start of the period of validity, as printed"),
    "validity_to": _s("End of the period of validity, as printed (may say 'Not Applicable' or 'Continuous')"),
})

COI_SCHEMA = _obj({
    "cin": _s("The 21-character Corporate Identity Number, e.g. U56101MH2021PTC123456"),
    "company_name": _s("Name of the company exactly as printed on the certificate"),
    "date_of_incorporation": _s("Date of incorporation as printed, DD/MM/YYYY"),
    "company_type": _s("Type of company, e.g. Private Limited Company, Company limited by shares"),
    "registered_office_address": _s("Registered office address, if printed on the certificate. Empty if not present"),
    "registrar": _s("Name of the Registrar of Companies office that issued the certificate"),
})

BOARD_RESOLUTION_SCHEMA = _obj({
    "company_name": _s("Name of the company passing the resolution"),
    "cin": _s("Corporate Identity Number of the company, if printed"),
    "resolution_date": _s("Date on which the board resolution was passed, DD/MM/YYYY"),
    "purpose": _s("What the resolution authorises, e.g. opening a merchant account with a payment gateway"),
    "authorised_signatory_name": _s("Full name of the person authorised to sign / operate on behalf of the company"),
    "authorised_signatory_designation": _s("Designation of the authorised signatory, e.g. Director, Authorised Signatory"),
    "resolution_signed_by": {"type": "array", "description": "Names of the directors who signed the resolution",
                             "items": _s("A director's full name")},
})

BANK_CHEQUE_SCHEMA = _obj({
    "account_holder_name": _s("Name of the account holder as pre-printed on the cheque or letter"),
    "account_number": _s("Bank account number, digits only"),
    "ifsc": _s("11-character IFSC code, e.g. HDFC0000128"),
    "bank_name": _s("Name of the bank"),
    "branch": _s("Branch name or address, if printed"),
    "account_type": _s("Type of account if stated, e.g. Current, Savings. Empty if not stated"),
})

DIRECTOR_KYC_SCHEMA = _obj({
    "full_name": _s("Full name of the person exactly as printed on the ID"),
    "id_type": _s("Type of ID document, e.g. Aadhaar (masked), PAN, Passport, Voter ID, Driving Licence"),
    "aadhaar_masked": _s("Masked Aadhaar number if present, e.g. XXXX XXXX 4821. Never output unmasked digits"),
    "pan_number": _s("10-character PAN if the document shows one"),
    "din": _s("Director Identification Number (8 digits) if shown"),
    "date_of_birth": _s("Date of birth, DD/MM/YYYY, if printed"),
    "address": _s("Address printed on the document, if any"),
})

SHAREHOLDING_SCHEMA = _obj({
    "company_name": _s("Name of the company whose shareholding is declared"),
    "as_of_date": _s("Date as of which the shareholding is declared, DD/MM/YYYY"),
    "shareholders": _arr(
        "Direct shareholders of the company, one entry per row of the shareholding table",
        {
            "name": _s("Name of the shareholder"),
            "holder_type": _s("One of: individual, company, llp, trust, other"),
            "percentage": _s("Percentage of shares held, number only, e.g. 40"),
        }, "One direct shareholder"),
    "entity_partners": _arr(
        "Owners of any corporate/LLP shareholder (look-through table). Empty if the declaration has none",
        {
            "entity_name": _s("Name of the corporate or LLP shareholder this row belongs to"),
            "partner_name": _s("Name of the partner / member / shareholder of that entity"),
            "percentage": _s("Percentage of the entity held by this partner, number only"),
        }, "One owner of a corporate shareholder"),
})

FSSAI_SCHEMA = _obj({
    "licence_number": _s("14-digit FSSAI licence / registration number"),
    "business_name": _s("Name of the food business operator exactly as printed"),
    "premises_address": _s("Address of the premises exactly as printed"),
    "licence_type": _s("Type, e.g. State Licence, Central Licence, Registration"),
    "kind_of_business": _s("Kind of business, e.g. Manufacturer, Trader, Restaurant"),
    "valid_from": _s("Issue / start date, DD/MM/YYYY"),
    "valid_until": _s("Expiry date, DD/MM/YYYY"),
})

ELECTRICITY_BILL_SCHEMA = _obj({
    "consumer_name": _s("Name of the consumer exactly as printed"),
    "consumer_number": _s("Consumer / account number"),
    "service_address": _s("Service / supply address of the connection exactly as printed"),
    "utility_name": _s("Name of the electricity distribution company"),
    "bill_date": _s("Bill date, DD/MM/YYYY"),
})

SCHEMAS: dict[str, dict] = {
    "pan": PAN_SCHEMA,
    "gst": GST_SCHEMA,
    "coi": COI_SCHEMA,
    "board_resolution": BOARD_RESOLUTION_SCHEMA,
    "bank_cheque": BANK_CHEQUE_SCHEMA,
    "director_kyc": DIRECTOR_KYC_SCHEMA,
    "shareholding": SHAREHOLDING_SCHEMA,
    "fssai": FSSAI_SCHEMA,
    "electricity_bill": ELECTRICITY_BILL_SCHEMA,
}


def _validate(node: dict, path: str = "root", depth: int = 1) -> list[str]:
    """Cheap local check of Sarvam's schema rules so we fail in tests, not on the API."""
    errs = []
    if not node.get("type"):
        errs.append(f"{path}: missing type")
    if path != "root" and not (node.get("description") or "").strip():
        errs.append(f"{path}: missing description")
    if depth > 4:
        errs.append(f"{path}: depth {depth} > 4")
    for k, v in (node.get("properties") or {}).items():
        errs += _validate(v, f"{path}.{k}", depth + 1)
    if isinstance(node.get("items"), dict):
        errs += _validate(node["items"], f"{path}[]", depth + 1)
    return errs


def validate_all() -> dict[str, list[str]]:
    return {k: _validate(v) for k, v in SCHEMAS.items() if _validate(v)}
