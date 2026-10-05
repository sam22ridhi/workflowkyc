"""Cross-document checks. The model READS the documents (Sarvam); this module CHECKS them.

Plain Python, no LLM: every result is repeatable and carries evidence. `evaluate()` is pure (case + documents +
registry in, checks out) so it is easy to test; `run()` persists the results, triages the case and writes the audit trail.

Each check:  {id, label, status: pass|fail|warn|skip, detail, evidence: [{doc_id, doc_type, field, page, value, source}],
              action: 'ask' | 'escalate' | None}
  ask       the merchant can fix it (re-upload / correct a document)
  escalate  needs human judgement (signatory authority, hidden beneficial owner)
Triage: any 'escalate' failure -> ESCALATE; else any failure or warning -> ASK; all pass/skip -> AUTO.
"""
import re
from datetime import date, datetime

from sqlmodel import Session, select

from app.checks.validators import CIN_RE, EXPECTED_4TH_CHAR, GSTIN_RE, PAN_RE, PAN_HOLDER_TYPES, name_match, normalise_name
from app.crm_form import SHORT, _differs
from app.db import audit, engine
from app.doctypes import DOC_TYPES, INDUSTRY_LICENCE, REQUIRED_DOCS, required_for
from app.models import Case, CheckResult, Document, utcnow
from app.registry import mock_registry

BO_THRESHOLD = 10.0           # beneficial ownership rule: more than 10%
REG = "MCA registry (MOCK)"
EXPECTED_PAN_CHAR = {**EXPECTED_4TH_CHAR, "proprietorship": "P"}
NO_CIN = {"llp", "partnership", "proprietorship"}
_TITLES = {"mr", "mrs", "ms", "dr", "shri", "smt", "sri", "mx"}


# ------------------------------------------------------------------ helpers
def _newest(docs: list) -> dict:
    out = {}
    for d in sorted(docs, key=lambda d: getattr(d, "created_at", None) or datetime.min):
        if getattr(d, "fields", None) and getattr(d, "status", "extracted") in {"extracted", "needs_attention"}:
            out[d.doc_type] = d
    return out


def _val(by_type: dict, doc_type: str, key: str):
    d = by_type.get(doc_type)
    v = ((d.fields or {}).get(key) or {}).get("value") if d else None
    return None if v in (None, "", []) else v


def _ev(by_type: dict, doc_type: str, key: str, value=None) -> dict:
    d = by_type[doc_type]
    f = (d.fields or {}).get(key) or {}
    return {"doc_id": d.id, "doc_type": doc_type, "field": key, "page": f.get("page"),
            "value": f.get("value") if value is None else value, "source": SHORT.get(doc_type, doc_type)}


def _app(field: str, value) -> dict:
    return {"doc_id": None, "doc_type": None, "field": field, "page": None, "value": value, "source": "Merchant application"}


def _reg(field: str, value) -> dict:
    return {"doc_id": None, "doc_type": None, "field": field, "page": None, "value": value, "source": REG}


def _check(id_: str, label: str, status: str, detail: str, evidence: list | None = None, action: str | None = None) -> dict:
    return {"id": id_, "label": label, "status": status, "detail": detail, "evidence": evidence or [],
            "action": action if status in {"fail", "warn"} else None}


def _ptoks(name: str) -> set[str]:
    return {t for t in re.sub(r"[^a-z ]", " ", (name or "").lower()).split() if t not in _TITLES}


def same_person(a: str, b: str) -> bool:
    """'Anil Sharma' == 'Mr. Anil Sharma' == 'Sharma Anil'; 'Anil Kumar Sharma' matches 'Anil Sharma'."""
    ta, tb = _ptoks(a), _ptoks(b)
    return bool(ta and tb) and (ta == tb or (min(len(ta), len(tb)) >= 2 and (ta <= tb or tb <= ta)))


def _upfirst(text: str) -> str:
    return text[:1].upper() + text[1:]


def _op_addr(case) -> str | None:
    """Where the merchant says they operate. Falls back to the registered address when no separate one is given."""
    return getattr(case, "operating_address", None) or case.registered_address


def _pct(x) -> float:
    try:
        return float(re.sub(r"[^0-9.]", "", str(x)) or 0)
    except ValueError:
        return 0.0


def _parse_date(s) -> date | None:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(s).strip(), fmt).date()
        except ValueError:
            continue
    return None


# ------------------------------------------------------------------ the 10 checks
def c1_legal_name(case, by_type) -> dict:
    label = "Legal name consistent across documents"
    srcs = [("pan", "holder_name"), ("gst", "legal_name"), ("coi", "company_name"), ("bank_cheque", "account_holder_name")]
    found = [(dt, k, _val(by_type, dt, k)) for dt, k in srcs if _val(by_type, dt, k)]
    bad_first = sorted(found, key=lambda t: normalise_name(t[2]) == normalise_name(case.legal_name))
    ev = [_app("legal_name", case.legal_name)] + [_ev(by_type, dt, k) for dt, k, _ in bad_first]
    if len(found) < 2:
        return _check("legal_name_consistent", label, "warn", f"Only {len(found)} document(s) carry the legal name, so it cannot be cross-checked yet.", ev, "ask")
    bad = [f"{SHORT[dt]} says “{v}”" for dt, k, v in found if normalise_name(v) != normalise_name(case.legal_name)]
    if bad:
        return _check("legal_name_consistent", label, "fail", f"Legal name on the application is “{case.legal_name}” but " + "; ".join(bad) + ".", ev, "ask")
    return _check("legal_name_consistent", label, "pass", f"{len(found)} documents match “{case.legal_name}” (ignoring Pvt/Private, Ltd/Limited and punctuation).", ev)


def c2_pan_type(case, by_type) -> dict:
    label = "PAN valid and matches entity type"
    pan = re.sub(r"\s", "", str(_val(by_type, "pan", "pan_number") or case.pan or "")).upper()
    ev = [_ev(by_type, "pan", "pan_number")] if "pan" in by_type and _val(by_type, "pan", "pan_number") else [_app("pan", case.pan)]
    if not PAN_RE.match(pan):
        return _check("pan_entity_type", label, "fail", f"“{pan or 'nothing'}” is not a valid PAN (AAAAA9999A).", ev, "ask")
    issues, expected = [], EXPECTED_PAN_CHAR.get(case.entity_type)
    if expected and pan[3] != expected:
        issues.append(f"4th character “{pan[3]}” means {PAN_HOLDER_TYPES.get(pan[3], 'unknown')}, but a {case.entity_type.replace('_', ' ')} should have “{expected}”")
    if case.pan and pan != case.pan.upper():
        issues.append(f"PAN document shows {pan} but the application says {case.pan}")
    if issues:
        return _check("pan_entity_type", label, "fail", "; ".join(issues) + ".", ev, "ask")
    return _check("pan_entity_type", label, "pass", f"{pan}: 4th character “{pan[3]}” = {PAN_HOLDER_TYPES.get(pan[3])}, consistent with a {case.entity_type.replace('_', ' ')}.", ev)


def c3_gstin_pan(case, by_type, registry) -> dict:
    label = "GSTIN embeds the company PAN"
    gstin = re.sub(r"\s", "", str(_val(by_type, "gst", "gstin") or "")).upper()
    pan = re.sub(r"\s", "", str(_val(by_type, "pan", "pan_number") or case.pan or "")).upper()
    if not gstin:
        return _check("gstin_pan", label, "skip", "No GST certificate has been read yet.")
    ev = [_ev(by_type, "gst", "gstin")] + ([_ev(by_type, "pan", "pan_number")] if _val(by_type, "pan", "pan_number") else [_app("pan", case.pan)])
    issues = []
    if not GSTIN_RE.match(gstin):
        issues.append(f"{gstin} is not a valid 15-character GSTIN")
    elif pan and gstin[2:12] != pan:
        issues.append(f"characters 3-12 of the GSTIN are {gstin[2:12]} but the PAN is {pan}")
    if case.gstin and gstin != case.gstin.upper():
        issues.append(f"GST certificate shows {gstin} but the application says {case.gstin}")
    g = (registry or {}).get("gst")
    if g:
        ev.append(_reg("gstin", g["gstin"]))
        if g["gstin"].upper() != gstin:
            issues.append(f"GST registry holds {g['gstin']}")
        elif g.get("status") != "Active":
            issues.append(f"GST registration status is {g.get('status')}")
    if issues:
        return _check("gstin_pan", label, "fail", "; ".join(issues) + ".", ev, "ask")
    return _check("gstin_pan", label, "pass", f"GSTIN {gstin} contains PAN {pan} in characters 3-12" + (" and is Active in the GST registry." if g else "."), ev)


def c4_cin(case, by_type, registry) -> dict:
    label = "CIN valid and matches the Certificate of Incorporation"
    if case.entity_type in NO_CIN:
        return _check("cin_match", label, "skip", f"A {case.entity_type.replace('_', ' ')} has no CIN.")
    cin = re.sub(r"\s", "", str(_val(by_type, "coi", "cin") or "")).upper()
    if not cin:
        return _check("cin_match", label, "warn", "No Certificate of Incorporation has been read yet.", [_app("cin", case.cin)], "ask")
    ev = [_ev(by_type, "coi", "cin"), _app("cin", case.cin)]
    issues = []
    if not CIN_RE.match(cin):
        issues.append(f"{cin} is not a valid 21-character CIN")
    if case.cin and cin != case.cin.upper():
        issues.append(f"certificate shows {cin} but the application says {case.cin}")
    m = (registry or {}).get("mca")
    if m:
        ev.append(_reg("cin", m["cin"]))
        if m["cin"].upper() != cin:
            issues.append(f"MCA record has {m['cin']}")
        if m.get("status") != "Active":
            issues.append(f"MCA status is {m.get('status')}")
        if normalise_name(m["name"]) != normalise_name(_val(by_type, "coi", "company_name") or m["name"]):
            issues.append(f"MCA name is “{m['name']}”")
    if issues:
        return _check("cin_match", label, "fail", "; ".join(issues) + ".", ev, "ask")
    return _check("cin_match", label, "pass", f"CIN {cin} is well-formed" + (" and matches the MCA record (Active)." if m else "."), ev)


def c5_signatory(case, by_type, registry) -> dict:
    label = "Board-resolution signatory is a current director"
    name = _val(by_type, "board_resolution", "authorised_signatory_name")
    if not name:
        return _check("signatory_is_director", label, "skip", "No board resolution has been read yet.")
    m = (registry or {}).get("mca")
    if not m or not m.get("directors"):
        return _check("signatory_is_director", label, "skip", "The registry has no director list for this entity.", [_ev(by_type, "board_resolution", "authorised_signatory_name")])
    dirs = [d["name"] for d in m["directors"]]
    ev = [_ev(by_type, "board_resolution", "authorised_signatory_name"), _reg("directors", ", ".join(dirs))]
    if any(same_person(name, d) for d in dirs):
        return _check("signatory_is_director", label, "pass", f"{name} is a current director per the MCA record.", ev)
    signed = _val(by_type, "board_resolution", "resolution_signed_by") or []
    extra = f" The resolution itself is signed by {', '.join(signed)}." if signed else ""
    return _check("signatory_is_director", label, "fail",
                  f"{name} is not a current director (MCA: {', '.join(dirs)}).{extra} A human must judge whether this is a valid delegation of authority.",
                  ev, "escalate")


def beneficial_owners(shareholders: list, partners: list) -> tuple[list[dict], list[dict]]:
    """Effective % per natural person, looking through corporate/LLP shareholders using the declared partner table.
    Returns (owners, unresolved_entities). owner = {name, total, direct, indirect: [{via, entity_pct, partner_pct, effective}]}"""
    owners: list[dict] = []
    unresolved: list[dict] = []

    def owner(name: str) -> dict:
        for o in owners:
            if same_person(o["name"], name):
                return o
        o = {"name": name, "total": 0.0, "direct": 0.0, "indirect": []}
        owners.append(o)
        return o

    for r in shareholders:
        pct, kind, name = _pct(r.get("percentage")), (r.get("holder_type") or "").lower(), r.get("name") or ""
        if kind in {"individual", "person", ""}:
            o = owner(name)
            o["direct"] += pct
            o["total"] += pct
            continue
        kids = [p for p in partners if normalise_name(p.get("entity_name", "")) == normalise_name(name)]
        if not kids:
            unresolved.append({"name": name, "percent": pct})
        for p in kids:
            eff = pct * _pct(p.get("percentage")) / 100
            o = owner(p.get("partner_name") or "")
            o["indirect"].append({"via": name, "entity_pct": pct, "partner_pct": _pct(p.get("percentage")), "effective": eff})
            o["total"] += eff
    return owners, unresolved


def c6_beneficial_owners(case, by_type, kyc_names, registry) -> dict:
    label = "Beneficial owners above 10% identified and KYC'd"
    sh = by_type.get("shareholding")
    if not sh:
        if case.entity_type in {"private_limited", "public_limited", "llp"}:
            return _check("beneficial_owners", label, "warn", "No shareholding / beneficial-owner declaration has been read yet.", [], "ask")
        return _check("beneficial_owners", label, "skip", "Not applicable for this entity type.")
    rows, partners = _val(by_type, "shareholding", "shareholders") or [], _val(by_type, "shareholding", "entity_partners") or []
    owners, unresolved = beneficial_owners(rows, partners)
    ev, ok_ev, issues, escalate = [], [], [], False
    big = sorted((o for o in owners if o["total"] > BO_THRESHOLD), key=lambda o: -o["total"])
    for o in big:
        has_kyc = any(same_person(o["name"], k) for k in kyc_names)
        if o["indirect"]:
            via = "; ".join(f"via {i['via']}: {i['partner_pct']:g}% of its {i['entity_pct']:g}%" for i in o["indirect"])
            how = f"{o['total']:g}% effective ({via})"
        else:
            how = f"{o['total']:g}% direct"
        (ok_ev if has_kyc else ev).append(
            _ev(by_type, "shareholding", "entity_partners" if o["indirect"] else "shareholders", f"{o['name']}: {how}"))
        if not has_kyc:
            issues.append(f"{o['name']} {how} has no KYC on file")
            escalate = escalate or bool(o["indirect"])
    for u in unresolved:
        issues.append(f"{u['name']} ({u['percent']:g}%) is a corporate shareholder with no look-through to its owners")
    m = (registry or {}).get("mca")
    if m and m.get("shareholding"):
        for rh in m["shareholding"]:
            hit = next((r for r in rows if normalise_name(r.get("name", "")) == normalise_name(rh["holder"]) or same_person(r.get("name", ""), rh["holder"])), None)
            if hit is None or abs(_pct(hit.get("percentage")) - rh["percent"]) > 1:
                issues.append(f"declared shareholding differs from the MCA record for {rh['holder']} (MCA: {rh['percent']}%)")
                ev.append(_reg("shareholding", f"{rh['holder']} {rh['percent']}%"))
                escalate = True
    ev += ok_ev                                            # owners without KYC first: findings quote the first one
    if issues:
        hidden = sum(1 for o in big if o["indirect"] and not any(same_person(o["name"], k) for k in kyc_names))
        tail = f" {hidden} hidden behind a corporate shareholder." if hidden else ""
        return _check("beneficial_owners", label, "fail", "; ".join(issues) + "." + tail, ev, "escalate" if escalate else "ask")
    return _check("beneficial_owners", label, "pass", f"{len(big)} owner(s) above {BO_THRESHOLD:g}% identified, all with KYC on file.", ev)


def c7_bank(case, by_type, registry) -> dict:
    label = "Bank account holder matches legal name"
    ch = by_type.get("bank_cheque")
    if not ch:
        return _check("bank_holder_name", label, "skip", "No cancelled cheque / bank letter has been read yet.")
    holder, acct = _val(by_type, "bank_cheque", "account_holder_name"), re.sub(r"\D", "", str(_val(by_type, "bank_cheque", "account_number") or ""))
    ev, issues = [_ev(by_type, "bank_cheque", "account_holder_name"), _app("legal_name", case.legal_name)], []
    m = name_match(holder or "", case.legal_name)
    if m == "suffix":
        issues.append(f"the cheque pre-prints “{holder}” but the legal name is “{case.legal_name}” (the company suffix is missing; the holder name must match exactly)")
    elif m == "different":
        issues.append(f"the cheque holder “{holder or 'nothing'}” does not match the legal name “{case.legal_name}”")
    at = str(_val(by_type, "bank_cheque", "account_type") or "").lower()
    if "saving" in at:
        issues.append("it is a savings account; corporate settlement needs a current account")
    pd = (registry or {}).get("penny_drop")
    if pd:
        ev.append(_reg("penny_drop", f"{pd['account_number']} · {pd['account_holder']}"))
        if acct and re.sub(r"\D", "", pd["account_number"]) != acct:
            ev.append(_ev(by_type, "bank_cheque", "account_number"))
            issues.append(f"the account number read from the cheque ({acct}) differs from the bank's penny-drop record ({pd['account_number']}); possible misread, ask for a clearer cheque")
        if name_match(pd["account_holder"], case.legal_name) != "same":
            issues.append(f"the bank's penny-drop returned the holder “{pd['account_holder']}”")
    if issues:
        return _check("bank_holder_name", label, "fail", _upfirst("; ".join(issues)) + ".", ev, "ask")
    return _check("bank_holder_name", label, "pass", f"Account holder “{holder}” matches the legal name" + (" and the penny-drop record." if pd else "."), ev)


def c8_address(case, by_type, registry) -> dict:
    label = "Address consistent (registered office / principal place / application)"
    reg_addr, op_addr = case.registered_address, _op_addr(case)
    coi, gst, fssai = (_val(by_type, "coi", "registered_office_address"), _val(by_type, "gst", "principal_place_address"),
                       _val(by_type, "fssai", "premises_address"))
    bill = _val(by_type, "electricity_bill", "service_address")
    if not (coi or gst or fssai or bill):
        return _check("address_consistent", label, "skip", "No document with an address has been read yet.")
    bad, good, issues = [], [], []
    app_ev = [_app("registered_address", reg_addr)] + ([_app("operating_address", op_addr)] if op_addr != reg_addr else [])
    if coi:
        e = _ev(by_type, "coi", "registered_office_address")
        if reg_addr and _differs("address", coi, reg_addr):
            issues.append(f"the Certificate of Incorporation gives “{coi}” but the application’s registered address is “{reg_addr}”")
            bad.append(e)
        else:
            good.append(e)
    if gst:
        e = _ev(by_type, "gst", "principal_place_address")
        g = (registry or {}).get("gst")
        gst_issues = []
        if op_addr and _differs("address", gst, op_addr):
            gst_issues.append(f"the GST certificate’s principal place says “{gst}” but the application says “{op_addr}”")
        if g and _differs("address", gst, g["principal_place"]):
            gst_issues.append(f"the GST registry holds “{g['principal_place']}”")
        (bad if gst_issues else good).append(e)
        issues += gst_issues
    if bill:
        e = _ev(by_type, "electricity_bill", "service_address")
        if op_addr and _differs("address", bill, op_addr):
            issues.append(f"the electricity bill's service address is “{bill}” but the application says “{op_addr}”")
            bad.append(e)
        else:
            good.append(e)
    if fssai and gst:
        e = _ev(by_type, "fssai", "premises_address")
        if _differs("address", fssai, gst):
            issues.append(f"the FSSAI premises “{fssai}” differ from the GST principal place")
            bad.append(e)
        else:
            good.append(e)
    ev = app_ev[:1] + bad + app_ev[1:] + good          # conflicting evidence first: findings quote it
    if issues:
        return _check("address_consistent", label, "fail", "Address drift: " + "; ".join(issues) + ".", ev, "ask")
    return _check("address_consistent", label, "pass", "All addresses agree with the application.", ev)


def c9_required_docs(case, by_type, all_docs) -> dict:
    label = "Required documents present"
    licence = INDUSTRY_LICENCE.get((case.industry or "").lower())
    required = [t for t in required_for(case.entity_type, case.industry) if t != licence]
    missing = [t for t in required if t not in by_type]
    unknown = [d.filename for d in all_docs if getattr(d, "doc_type", "") == "unknown"]
    if missing:
        return _check("required_documents", label, "fail", f"Missing for a {case.entity_type.replace('_', ' ')}: " + ", ".join(DOC_TYPES[t] for t in missing) + ".", [], "ask")
    if unknown:
        return _check("required_documents", label, "warn", f"All required documents are present, but {len(unknown)} file(s) could not be classified: {', '.join(unknown)}.", [], "ask")
    return _check("required_documents", label, "pass", f"All {len(required)} required documents are present.", [])


def c10_licence(case, by_type, today: date) -> dict:
    label = "Industry licence present and valid"
    licence = INDUSTRY_LICENCE.get((case.industry or "").lower())
    if not licence:
        return _check("licence", label, "skip", f"No licence is required for the “{case.industry or 'unspecified'}” industry.")
    name = DOC_TYPES[licence]
    if licence not in by_type:
        return _check("licence", label, "fail", f"{name} is required for the {case.industry} industry but has not been uploaded.", [], "ask")
    ev, issues = [_ev(by_type, licence, "licence_number"), _ev(by_type, licence, "valid_until")], []
    until = _parse_date(_val(by_type, licence, "valid_until"))
    if until is None:
        issues.append("the expiry date could not be read")
    elif until < today:
        issues.append(f"it expired on {until:%d/%m/%Y}")
    holder = _val(by_type, licence, "business_name")
    if holder and normalise_name(holder) != normalise_name(case.legal_name):
        issues.append(f"it is issued to “{holder}”, not “{case.legal_name}”")
    if issues:
        return _check("licence", label, "fail", f"{name}: " + "; ".join(issues) + ".", ev, "ask")
    return _check("licence", label, "pass", f"{name} {_val(by_type, licence, 'licence_number')} is valid until {until:%d/%m/%Y}.", ev)


# ------------------------------------------------------------------ evaluate / triage / run
def evaluate(case, docs: list, registry: dict | None, today: date | None = None) -> list[dict]:
    """Pure: run all 10 checks. `docs` are Document-like objects (id, doc_type, fields, status, filename, created_at)."""
    today = today or date.today()
    by_type = _newest(docs)
    kyc_names = [str((d.fields or {}).get("full_name", {}).get("value") or "") for d in docs
                 if d.doc_type == "director_kyc" and d.fields]
    return [
        c1_legal_name(case, by_type), c2_pan_type(case, by_type), c3_gstin_pan(case, by_type, registry),
        c4_cin(case, by_type, registry), c5_signatory(case, by_type, registry),
        c6_beneficial_owners(case, by_type, kyc_names, registry), c7_bank(case, by_type, registry),
        c8_address(case, by_type, registry), c9_required_docs(case, by_type, docs), c10_licence(case, by_type, today),
    ]


def triage(checks: list[dict]) -> str:
    if any(c["status"] == "fail" and c["action"] == "escalate" for c in checks):
        return "ESCALATE"
    if any(c["status"] in {"fail", "warn"} for c in checks):
        return "ASK"
    return "AUTO"


def summarise(checks: list[dict], route: str) -> str:
    bad = [c for c in checks if c["status"] in {"fail", "warn"}]
    passed = sum(1 for c in checks if c["status"] == "pass")
    if route == "AUTO":
        return f"All {passed} applicable checks passed. Ready for one-click KAM approval."
    esc = [c["label"] for c in bad if c["action"] == "escalate"]
    ask = [c["label"] for c in bad if c["action"] != "escalate"]
    parts = []
    if esc:
        parts.append(f"{len(esc)} need human judgement ({'; '.join(esc)})")
    if ask:
        parts.append(f"{len(ask)} the merchant can fix ({'; '.join(ask)})")
    head = f"{len(bad)} issue{'s' if len(bad) != 1 else ''} found, {passed} checks passed: "
    return head + " and ".join(parts) + (". Escalate to a KAM decision." if route == "ESCALATE" else ". Karyakarta can chase the merchant by voice, WhatsApp or email.")


def run(case_id: str) -> dict:
    """Persist the checks for a case, triage it, update stage/status and write the audit trail. Never raises on data."""
    with Session(engine) as s:
        case = s.get(Case, case_id)
        if case is None:
            raise LookupError(case_id)
        docs = list(s.exec(select(Document).where(Document.case_id == case_id)))
        registry = mock_registry.lookup(case_id)
        checks = evaluate(case, docs, registry)
        route = triage(checks)
        summary = summarise(checks, route)

        for old in s.exec(select(CheckResult).where(CheckResult.case_id == case_id)):
            s.delete(old)
        for c in checks:
            s.add(CheckResult(case_id=case_id, check_id=c["id"], label=c["label"], status=c["status"], detail=c["detail"],
                              evidence=c["evidence"], action=c["action"]))
        case.route, case.summary, case.updated_at = route, summary, utcnow()
        case.stage = max(case.stage, 4)                       # AI verification done: the case is now in KAM review
        case.status = {"AUTO": "ready_for_review", "ASK": "awaiting_merchant", "ESCALATE": "needs_attention"}[route]
        s.add(case)
        s.commit()

        issues = [c for c in checks if c["status"] in {"fail", "warn"}]
        for c in issues:
            audit(s, case_id, "agent", f"Issue: {c['label']}", c["detail"][:300],
                  "warning", next((e["doc_id"] for e in c["evidence"] if e.get("doc_id")), None))
        audit(s, case_id, "agent", f"Cross-check complete · route {route}", summary,
              "success" if route == "AUTO" else "warning")
        return {"case_id": case_id, "route": route, "summary": summary, "checks": checks, "issues": issues,
                "counts": {st: sum(1 for c in checks if c["status"] == st) for st in ("pass", "fail", "warn", "skip")},
                "registry": registry["label"]}
