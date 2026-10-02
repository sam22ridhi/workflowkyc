"""Cross-document checks on the Sharma Foods hero case. Document fields mirror what Sarvam really extracted."""
import copy
from datetime import date
from itertools import count
from types import SimpleNamespace

import pytest
from sqlmodel import Session, select

from app.checks import cross_check as cc
from app.db import engine
from app.models import Case, CheckResult, Document
from app.registry import mock_registry

_ids = count(1)


def F(value, page=1):
    return {"value": value, "page": page, "confidence": 99.0, "box": None}


def doc(doc_type, **fields):
    return SimpleNamespace(id=f"d{next(_ids)}", doc_type=doc_type, filename=f"{doc_type}.pdf", status="extracted",
                           created_at=None, fields={k: F(v) for k, v in fields.items()})


CASE = SimpleNamespace(id="KYB-20814", legal_name="Sharma Foods Private Limited", entity_type="private_limited", industry="food",
                       cin="U56101MH2021PTC123456", pan="AABCS1429E", gstin="27AABCS1429E1Z8",
                       registered_address="12 MG Road, Mumbai - 400001, Maharashtra")

SHAREHOLDERS = [{"name": "Anil Sharma", "holder_type": "individual", "percentage": "40"},
                {"name": "Priya Sharma", "holder_type": "individual", "percentage": "30"},
                {"name": "Sharma Holdings LLP", "holder_type": "llp", "percentage": "30"}]
FIXED_CASE = SimpleNamespace(**{**CASE.__dict__, "operating_address": "12 Mahatma Gandhi Marg, Navi Mumbai - 400703, Maharashtra"})
PARTNERS = [{"entity_name": "Sharma Holdings LLP", "partner_name": "Rakesh Sharma", "percentage": "60"},
            {"entity_name": "Sharma Holdings LLP", "partner_name": "Meera Sharma", "percentage": "40"}]


def hero_docs():
    """The eight documents exactly as extracted, planted issues included."""
    return [
        doc("pan", pan_number="AABCS1429E", holder_name="SHARMA FOODS PRIVATE LIMITED", date="14/08/2021"),
        doc("gst", gstin="27AABCS1429E1Z8", legal_name="SHARMA FOODS PRIVATE LIMITED", trade_name="Sharma Foods",
            principal_place_address="12 Mahatma Gandhi Marg, Navi Mumbai - 400703, Maharashtra"),
        doc("coi", cin="U56101MH2021PTC123456", company_name="SHARMA FOODS PRIVATE LIMITED", date_of_incorporation="14/08/2021",
            registered_office_address="12 MG Road, Mumbai - 400001, Maharashtra"),
        doc("board_resolution", company_name="SHARMA FOODS PRIVATE LIMITED", authorised_signatory_name="Ravish Sahay",
            resolution_signed_by=["Anil Sharma", "Priya Sharma"]),
        doc("bank_cheque", account_holder_name="Sharma Foods", account_number="50200034928174", ifsc="HDFC0000128", account_type="Current"),
        doc("director_kyc", full_name="Anil Sharma", din="08492019", aadhaar_masked="XXXX XXXX 4821"),
        doc("shareholding", company_name="Sharma Foods Private Limited", shareholders=SHAREHOLDERS, entity_partners=PARTNERS),
        doc("fssai", licence_number="11521999000123", business_name="SHARMA FOODS PRIVATE LIMITED",
            premises_address="12 Mahatma Gandhi Marg, Navi Mumbai - 400703", valid_until="09/10/2030"),
    ]


TODAY = date(2026, 10, 2)
REGISTRY = mock_registry.lookup("KYB-20814")


def run_checks(docs, registry=REGISTRY, case=CASE):
    return {c["id"]: c for c in cc.evaluate(case, docs, registry, today=TODAY)}


def fixed_docs():
    """Hero documents with every planted issue corrected and the extra KYC supplied."""
    docs = hero_docs()
    by = {d.doc_type: d for d in docs}
    by["bank_cheque"].fields["account_holder_name"]["value"] = "Sharma Foods Private Limited"
    by["board_resolution"].fields["authorised_signatory_name"]["value"] = "Priya Sharma"
    docs += [doc("director_kyc", full_name=n) for n in ("Priya Sharma", "Rakesh Sharma", "Meera Sharma")]
    return docs


# ---------------------------------------------------------------- the four planted issues
def test_hero_case_finds_all_four_planted_issues_with_evidence():
    r = run_checks(hero_docs())

    bank = r["bank_holder_name"]                                    # 1. cheque name != legal name
    assert bank["status"] == "fail" and bank["action"] == "ask"
    assert "Sharma Foods" in bank["detail"] and "Sharma Foods Private Limited" in bank["detail"]
    assert {e["source"] for e in bank["evidence"]} >= {"Cancelled Cheque", "Merchant application"}

    sig = r["signatory_is_director"]                                # 2. signatory not a director
    assert sig["status"] == "fail" and sig["action"] == "escalate"
    assert "Ravish Sahay" in sig["detail"] and "Anil Sharma" in sig["detail"] and "Priya Sharma" in sig["detail"]
    assert any(e["doc_id"] for e in sig["evidence"]) and any(e["source"] == cc.REG for e in sig["evidence"])

    bo = r["beneficial_owners"]                                     # 3. hidden beneficial owner (18%)
    assert bo["status"] == "fail" and bo["action"] == "escalate"
    assert "Rakesh Sharma 18% effective" in bo["detail"] and "60% of its 30%" in bo["detail"]
    assert "hidden behind a corporate shareholder" in bo["detail"]
    assert any("Rakesh Sharma" in str(e["value"]) and e["doc_type"] == "shareholding" for e in bo["evidence"])
    assert "Anil Sharma" not in bo["evidence"][0]["value"] and "Anil Sharma" in bo["evidence"][-1]["value"]   # offenders first, compliant owner last
    assert "Anil Sharma" not in bo["detail"].split("have no KYC")[0] or "Anil Sharma 40% direct has no KYC" not in bo["detail"]

    addr = r["address_consistent"]                                  # 4. address drift Navi Mumbai vs Mumbai
    assert addr["status"] == "fail" and addr["action"] == "ask"
    assert "Navi Mumbai" in addr["detail"] and "12 MG Road, Mumbai" in addr["detail"]
    assert addr["evidence"][1]["source"] == "GST Cert"                  # conflicting evidence listed first (after the application value)
    assert {"GST Cert", "Merchant application"} <= {e["source"] for e in addr["evidence"]}


def test_hero_case_other_checks_pass_and_route_is_escalate():
    r = run_checks(hero_docs())
    for ok in ("legal_name_consistent", "pan_entity_type", "gstin_pan", "cin_match", "required_documents", "licence"):
        assert r[ok]["status"] == "pass", (ok, r[ok]["detail"])
    checks = list(r.values())
    assert len(checks) == 10 and cc.triage(checks) == "ESCALATE"
    s = cc.summarise(checks, "ESCALATE")
    assert "4 issues found" in s and "human judgement" in s and "merchant can fix" in s


def test_every_check_has_the_documented_shape():
    for c in run_checks(hero_docs()).values():
        assert set(c) == {"id", "label", "status", "detail", "evidence", "action"}
        assert c["status"] in {"pass", "fail", "warn", "skip"}
        for e in c["evidence"]:
            assert set(e) == {"doc_id", "doc_type", "field", "page", "value", "source"}


# ---------------------------------------------------------------- triage
def test_fixed_documents_route_auto():
    r = run_checks(fixed_docs(), case=FIXED_CASE)
    assert all(c["status"] in {"pass", "skip"} for c in r.values()), {k: v["detail"] for k, v in r.items() if v["status"] not in {"pass", "skip"}}
    assert cc.triage(list(r.values())) == "AUTO"
    assert "Ready for one-click KAM approval" in cc.summarise(list(r.values()), "AUTO")


def test_merchant_fixable_issues_only_route_ask():
    docs = fixed_docs()
    next(d for d in docs if d.doc_type == "bank_cheque").fields["account_holder_name"]["value"] = "Sharma Foods"
    assert cc.triage(list(run_checks(docs, case=FIXED_CASE).values())) == "ASK"


def test_missing_documents_are_reported():
    docs = [d for d in fixed_docs() if d.doc_type not in {"coi", "fssai"}]
    r = run_checks(docs, case=FIXED_CASE)
    assert r["required_documents"]["status"] == "fail" and "Certificate of Incorporation" in r["required_documents"]["detail"]
    assert r["licence"]["status"] == "fail" and "FSSAI" in r["licence"]["detail"]          # licence reported once, by check 10
    assert "FSSAI" not in r["required_documents"]["detail"]


# ---------------------------------------------------------------- individual rules
def test_pan_type_and_gstin_embedding():
    docs = fixed_docs()
    next(d for d in docs if d.doc_type == "pan").fields["pan_number"]["value"] = "AABPS1429E"   # 4th char P = individual
    assert run_checks(docs, case=FIXED_CASE)["pan_entity_type"]["status"] == "fail"
    docs = fixed_docs()
    next(d for d in docs if d.doc_type == "gst").fields["gstin"]["value"] = "27AABCS9999E1Z8"
    r = run_checks(docs, case=FIXED_CASE)["gstin_pan"]
    assert r["status"] == "fail" and "AABCS9999E" in r["detail"]


def test_cin_format_and_mismatch():
    docs = fixed_docs()
    next(d for d in docs if d.doc_type == "coi").fields["cin"]["value"] = "U56101MH2021PTC12345"   # 20 chars
    assert run_checks(docs, case=FIXED_CASE)["cin_match"]["status"] == "fail"


def test_llp_has_no_cin_check():
    llp = SimpleNamespace(**{**CASE.__dict__, "entity_type": "llp"})
    assert run_checks(fixed_docs(), case=llp)["cin_match"]["status"] == "skip"


def test_ocr_misread_account_number_is_caught_by_penny_drop():
    docs = fixed_docs()
    next(d for d in docs if d.doc_type == "bank_cheque").fields["account_number"]["value"] = "500034928174"  # the real Sarvam misread
    r = run_checks(docs, case=FIXED_CASE)["bank_holder_name"]
    assert r["status"] == "fail" and "500034928174" in r["detail"] and "50200034928174" in r["detail"] and "misread" in r["detail"]


def test_savings_account_rejected():
    docs = fixed_docs()
    next(d for d in docs if d.doc_type == "bank_cheque").fields["account_type"]["value"] = "Savings"
    assert "savings account" in run_checks(docs, case=FIXED_CASE)["bank_holder_name"]["detail"]


def test_expired_or_foreign_licence():
    docs = fixed_docs()
    fs = next(d for d in docs if d.doc_type == "fssai")
    fs.fields["valid_until"]["value"] = "01/01/2026"
    assert "expired on 01/01/2026" in run_checks(docs, case=FIXED_CASE)["licence"]["detail"]
    fs.fields["valid_until"]["value"] = "09/10/2030"
    fs.fields["business_name"]["value"] = "Someone Else Traders"
    assert run_checks(docs, case=FIXED_CASE)["licence"]["status"] == "fail"


def test_beneficial_owner_look_through_math():
    owners, unresolved = cc.beneficial_owners(SHAREHOLDERS, PARTNERS)
    by = {o["name"]: o for o in owners}
    assert by["Anil Sharma"]["total"] == 40 and by["Priya Sharma"]["total"] == 30
    assert by["Rakesh Sharma"]["total"] == pytest.approx(18.0) and by["Meera Sharma"]["total"] == pytest.approx(12.0)
    assert by["Rakesh Sharma"]["indirect"][0]["via"] == "Sharma Holdings LLP" and not unresolved
    # exactly 10% is NOT above the threshold
    ten, _ = cc.beneficial_owners([{"name": "Holdco Ltd", "holder_type": "company", "percentage": "50"}],
                                  [{"entity_name": "Holdco Limited", "partner_name": "Zed Zed", "percentage": "20"}])
    assert ten[0]["total"] == pytest.approx(10.0) and not ten[0]["total"] > cc.BO_THRESHOLD


def test_corporate_shareholder_without_look_through_is_flagged():
    docs = fixed_docs()
    next(d for d in docs if d.doc_type == "shareholding").fields["entity_partners"]["value"] = []
    r = run_checks(docs, case=FIXED_CASE)["beneficial_owners"]
    assert r["status"] == "fail" and "no look-through" in r["detail"]


def test_declaration_differing_from_registry_escalates():
    docs = fixed_docs()
    next(d for d in docs if d.doc_type == "shareholding").fields["shareholders"]["value"][0]["percentage"] = "55"
    r = run_checks(docs, case=FIXED_CASE)["beneficial_owners"]
    assert r["status"] == "fail" and r["action"] == "escalate" and "differs from the MCA record" in r["detail"]


def test_same_person_matching():
    assert cc.same_person("Anil Sharma", "Mr. Anil Sharma") and cc.same_person("Sharma Anil", "Anil Sharma")
    assert cc.same_person("Anil Kumar Sharma", "Anil Sharma")
    assert not cc.same_person("Ravish Sahay", "Priya Sharma") and not cc.same_person("Sharma", "Anil Sharma")


def test_name_consistency_normalises_suffixes_but_catches_real_differences():
    docs = fixed_docs()
    next(d for d in docs if d.doc_type == "gst").fields["legal_name"]["value"] = "SHARMA FOODS PVT. LTD."
    assert run_checks(docs, case=FIXED_CASE)["legal_name_consistent"]["status"] == "pass"
    next(d for d in docs if d.doc_type == "gst").fields["legal_name"]["value"] = "SHARMA TRADERS PRIVATE LIMITED"
    r = run_checks(docs, case=FIXED_CASE)["legal_name_consistent"]
    assert r["status"] == "fail" and "GST Cert" in r["detail"]


def test_mock_registry_is_labelled_and_covers_all_cases():
    assert "MOCK" in mock_registry.lookup("KYB-20814")["label"]
    for cid in ("KYB-20814", "KYB-20815", "KYB-20816", "KYB-20817", "KYB-20818"):
        assert mock_registry.lookup(cid)["gst"]["gstin"]
    assert mock_registry.lookup("NOPE")["mca"] is None


# ---------------------------------------------------------------- persisted run + route
@pytest.fixture
def hero_in_db():
    """Insert the hero documents; remove them (and the persisted checks) afterwards so other tests see a clean case."""
    with Session(engine) as s:
        for d in hero_docs():
            s.add(Document(id=f"cc_{d.id}", case_id="KYB-20814", doc_type=d.doc_type, filename=d.filename, path="x",
                           mime="application/pdf", size_bytes=1, sha256="0" * 64, status="extracted", fields=copy.deepcopy(d.fields)))
        s.commit()
    yield
    with Session(engine) as s:
        for row in list(s.exec(select(Document).where(Document.id.like("cc_%")))) + list(s.exec(select(CheckResult).where(CheckResult.case_id == "KYB-20814"))):
            s.delete(row)
        case = s.get(Case, "KYB-20814")
        case.route, case.summary, case.status, case.stage = None, None, "docs_pending", 2
        s.add(case)
        s.commit()


def test_run_persists_checks_route_and_audit_trail(client, hero_in_db):
    r = client.post("/api/cases/KYB-20814/cross-check")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["route"] == "ESCALATE" and len(data["issues"]) == 4 and len(data["checks"]) == 10     # n8n: issues.length > 0
    assert data["counts"] == {"pass": 6, "fail": 4, "warn": 0, "skip": 0} and "MOCK" in data["registry"]

    case = client.get("/api/cases/KYB-20814").json()["data"]
    assert case["route"] == "ESCALATE" and case["status"] == "needs_attention" and case["stage"] == 4
    assert {f["id"] for f in case["findings"]} == {"bank_holder_name", "signatory_is_director", "beneficial_owners", "address_consistent"}
    addr = next(f for f in case["findings"] if f["id"] == "address_consistent")
    assert "Mumbai" in addr["applicationValue"] and "Navi Mumbai" in addr["sourceValue"]
    assert "human judgement" in case["summary"]
    titles = [t["title"] for t in case["timeline"]]
    assert "Cross-check complete · route ESCALATE" in titles and any(t.startswith("Issue: Beneficial owners") for t in titles)

    rows = client.get("/api/cases").json()["data"]
    hero = next(c for c in rows["items"] if c["id"] == "KYB-20814")
    assert hero["route"] == "ESCALATE" and hero["isUrgent"] and rows["kpis"]["escalations"] == 1
    assert hero["stage"] == "Escalated to KAM" and rows["kpis"]["awaitingMerchant"] == 1     # only Royal Rajasthan waits on the merchant; escalated != waiting
    assert sum(1 for f in hero["flags"] if f["severity"] == "critical") == 4

    again = client.post("/api/cases/KYB-20814/cross-check").json()["data"]       # idempotent: rows replaced, not duplicated
    assert len(client.get("/api/cases/KYB-20814").json()["data"]["checks"]) == 10 and again["route"] == "ESCALATE"


def test_cross_check_unknown_case_404(client):
    assert client.post("/api/cases/NOPE/cross-check").status_code == 404
    assert client.get("/api/mock-registry/KYB-20814").json()["data"]["gst"]["status"] == "Active"
