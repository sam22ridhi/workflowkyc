"""Auto-filled CRM form: every field is built from extracted document fields, with a source citation,
confidence, a link back to the evidence box, and a conflict marker when sources disagree."""
from sqlmodel import Session, select

from app.checks.validators import name_match
from app.models import Case, CrmOverride, Document

SHORT = {"pan": "Company PAN", "gst": "GST Cert", "coi": "COI", "board_resolution": "Board Resolution",
         "bank_cheque": "Cancelled Cheque", "director_kyc": "Director KYC", "shareholding": "Shareholding Decl.",
         "fssai": "FSSAI Licence"}

# (key, label, kind, [(doc_type, field)], case attribute holding the merchant-application value)
# kind "name": compared with name_match (Pvt/Private equal; a dropped "Private Limited" is a conflict).
# kind "address": equal if one contains the other (trailing state/country); otherwise a conflict.
SECTIONS = [
    ("business", "Business & Entity Details", [
        ("legal_name", "Legal Entity Name", "name", [("coi", "company_name"), ("gst", "legal_name"), ("pan", "holder_name")], "legal_name"),
        ("cin", "Corporate Identity Number (CIN)", "text", [("coi", "cin")], "cin"),
        ("date_of_incorporation", "Date of Incorporation", "text", [("coi", "date_of_incorporation"), ("pan", "date")], None),
        ("registered_office", "Registered Office Address", "address", [("coi", "registered_office_address")], "registered_address"),
        ("principal_address", "Operating / Principal Address", "address", [("gst", "principal_place_address"), ("fssai", "premises_address")], "application_operating_address"),
        ("company_type", "Company Classification", "text", [("coi", "company_type"), ("gst", "constitution_of_business")], None),
        ("trade_name", "Trade Name", "text", [("gst", "trade_name")], None),
    ]),
    ("tax_bank", "Tax & Settlement Banking", [
        ("pan", "Permanent Account Number (PAN)", "text", [("pan", "pan_number")], "pan"),
        ("gstin", "GSTIN Identifier", "text", [("gst", "gstin")], "gstin"),
        ("bank_account", "Settlement Bank Account Number", "text", [("bank_cheque", "account_number")], None),
        ("ifsc", "Bank IFSC Code", "text", [("bank_cheque", "ifsc")], None),
        ("bank_holder", "Beneficiary / Account Holder Name", "name", [("bank_cheque", "account_holder_name")], "legal_name"),
        ("account_type", "Account Type", "text", [("bank_cheque", "account_type")], None),
        ("bank_name", "Bank", "text", [("bank_cheque", "bank_name")], None),
    ]),
    ("stakeholders", "Stakeholders & Beneficial Owners (KBO)", [
        ("signatory", "Authorised Signatory (Board Resolution)", "text", [("board_resolution", "authorised_signatory_name")], None),
        ("fssai", "FSSAI Licence Number", "text", [("fssai", "licence_number")], None),
    ]),
]


def _norm(v) -> str:
    return "".join(ch for ch in str(v).lower() if ch.isalnum())


def _newest_by_type(docs: list[Document]) -> dict[str, Document]:
    out: dict[str, Document] = {}
    for d in sorted(docs, key=lambda d: d.created_at):
        if d.fields and d.status in {"extracted", "needs_attention"}:
            out[d.doc_type] = d
    return out


def _cand(d: Document, key: str) -> dict | None:
    f = (d.fields or {}).get(key) or {}
    if f.get("value") in (None, "", []):
        return None
    page = f" p.{f['page']}" if f.get("page") else ""
    return {"value": str(f["value"]), "doc_id": d.id, "doc_type": d.doc_type, "field": key, "page": f.get("page"),
            "confidence": f.get("confidence"), "has_box": bool(f.get("box") or f.get("boxes")),
            "source": f"Source: {SHORT.get(d.doc_type, d.doc_type)}{page}"}


def _differs(kind: str, a: str, b: str) -> bool:
    if kind == "name":
        return name_match(a, b) != "same"
    na, nb = _norm(a), _norm(b)
    if kind == "address":   # "..., Navi Mumbai - 400703" vs the same with ", Maharashtra" appended is not a conflict
        shorter, longer = sorted((na, nb), key=len)
        return not (len(shorter) >= 12 and shorter in longer)
    return na != nb


def build(session: Session, case: Case) -> dict:
    docs = list(session.exec(select(Document).where(Document.case_id == case.id)))
    by_type = _newest_by_type(docs)
    overrides = {o.key: o for o in
                 session.exec(select(CrmOverride).where(CrmOverride.case_id == case.id).order_by(CrmOverride.id))}
    stats = {"filled": 0, "total": 0, "conflicts": 0, "confs": []}

    def make(key: str, label: str, kind: str, cands: list[dict], app_value: str | None) -> dict:
        stats["total"] += 1
        primary = cands[0] if cands else None
        others = [{"value": c["value"], "source": c["source"], "doc_id": c["doc_id"]} for c in cands[1:]]
        if app_value:
            others.append({"value": app_value, "source": "Source: Merchant application", "doc_id": None})
        diffs = [o for o in others if primary and _differs(kind, primary["value"], o["value"])]
        ov = overrides.get(key)
        value = ov.value if ov else (primary["value"] if primary else None)
        stats["filled"] += bool(value)
        if primary and primary["confidence"] is not None:
            stats["confs"].append(primary["confidence"])
        conflict = bool(diffs) and not ov
        stats["conflicts"] += conflict
        source = f"Source: KAM override ({ov.actor})" if ov else (primary["source"] if primary else "Awaiting document")
        return {"key": key, "label": label, "value": value, "ai_value": primary["value"] if primary else None,
                "overridden": bool(ov), "source": source,
                "doc_id": primary["doc_id"] if primary else None, "doc_type": primary["doc_type"] if primary else None,
                "field": primary["field"] if primary else None, "page": primary["page"] if primary else None,
                "confidence": primary["confidence"] if primary else None, "has_box": bool(primary and primary["has_box"]),
                "status": "missing" if not value else "conflict" if conflict else "ok",
                "conflict_note": "; ".join(f"{d['source']} says “{d['value']}”" for d in diffs) if conflict else None,
                "alternatives": others}

    sections = []
    for sid, title, specs in SECTIONS:
        fields = []
        for key, label, kind, srcs, app_attr in specs:
            cands = [c for dt, fk in srcs if dt in by_type for c in [_cand(by_type[dt], fk)] if c]
            fields.append(make(key, label, kind, cands, getattr(case, app_attr, None) if app_attr else None))
        if sid == "stakeholders":
            for d in sorted((d for d in docs if d.doc_type == "director_kyc" and d.fields), key=lambda d: d.created_at):
                name, din = _cand(d, "full_name"), _cand(d, "din")
                if name:
                    value = name["value"] + (f" · DIN {din['value']}" if din else "")
                    fields.append(make(f"director_{d.id}", "Director (KYC)", "text", [{**name, "value": value}], None))
            sh = by_type.get("shareholding")
            rows = (((sh.fields or {}).get("shareholders") or {}).get("value") or []) if sh else []
            for i, row in enumerate(rows):
                c = _cand(sh, "shareholders")
                value = f"{row.get('name')} · {row.get('percentage')}% ({row.get('holder_type')})"
                fields.append(make(f"shareholder_{i}", "Direct shareholder", "text", [{**c, "value": value}], None))
        sections.append({"id": sid, "title": title, "fields": fields})

    confs = stats["confs"]
    return {"case_id": case.id, "sections": sections,
            "summary": {"source_documents": len(by_type), "fields_total": stats["total"],
                        "fields_filled": stats["filled"],
                        "fill_percent": int(100 * stats["filled"] / stats["total"]) if stats["total"] else 0,
                        "conflicts": stats["conflicts"],
                        "avg_confidence": round(sum(confs) / len(confs), 1) if confs else None,
                        "missing_documents": [t for t in SHORT if t not in by_type]}}
