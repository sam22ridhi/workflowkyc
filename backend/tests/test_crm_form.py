import json
from pathlib import Path

from sqlmodel import Session

from app.db import engine
from app.models import Document
from app.sarvam.normalise import locate_boxes, to_fields
from app.sarvam.schemas import SCHEMAS

FX = Path(__file__).parent / "fixtures"


def _doc(case_id, doc_type, fields, name):
    with Session(engine) as s:
        s.add(Document(id=f"t_{doc_type}_{case_id}", case_id=case_id, doc_type=doc_type, filename=name, path="x",
                       mime="application/pdf", size_bytes=1, sha256="0" * 64, status="extracted", fields=fields))
        s.commit()


def test_crm_form_sources_conflicts_and_override(client):
    ex, dg = (json.loads((FX / f"GST_Certificate.{k}.json").read_text(encoding="utf-8")) for k in ("extract", "digitise"))
    _doc("KYB-20816", "gst", locate_boxes(to_fields(ex, SCHEMAS["gst"]), dg), "GST_Certificate.pdf")
    _doc("KYB-20816", "bank_cheque",
         {"account_holder_name": {"value": "Zenith Technologies", "page": 1, "confidence": 99.0, "box": None},
          "account_number": {"value": "123456789012", "page": 1, "confidence": 99.0, "box": None}}, "cheque.pdf")

    form = client.get("/api/cases/KYB-20816/crm-form").json()["data"]
    fields = {f["key"]: f for s in form["sections"] for f in s["fields"]}

    assert fields["gstin"]["value"] == "27AABCS1429E1Z8"
    assert fields["gstin"]["source"] == "Source: GST Cert p.1" and fields["gstin"]["has_box"] and fields["gstin"]["doc_id"]
    assert fields["cin"]["status"] == "missing" and fields["cin"]["source"] == "Awaiting document"
    # the GST principal place differs from the application address -> conflict with both values shown
    assert fields["principal_address"]["status"] == "conflict"
    assert "Merchant application" in fields["principal_address"]["conflict_note"]
    # "Zenith Technologies" vs "Zenith Technologies Private Limited" is a name conflict (suffix dropped)
    assert fields["bank_holder"]["status"] == "conflict"
    assert form["summary"]["conflicts"] >= 2 and "coi" in form["summary"]["missing_documents"]

    r = client.post("/api/cases/KYB-20816/crm-form/override",
                    json={"key": "bank_holder", "value": "Zenith Technologies Private Limited", "note": "bank letter attached"})
    assert r.status_code == 200
    f = {f["key"]: f for s in r.json()["data"]["sections"] for f in s["fields"]}["bank_holder"]
    assert f["overridden"] and f["ai_value"] == "Zenith Technologies" and f["status"] == "ok"
    assert client.post("/api/cases/KYB-20816/crm-form/override", json={"key": "nope", "value": "x"}).status_code == 400
    tl = client.get("/api/cases/KYB-20816").json()["data"]["timeline"]
    assert any(t["title"] == "CRM field overridden" for t in tl)


def test_name_match_tiers():
    from app.checks.validators import name_match
    assert name_match("Sharma Foods Pvt. Ltd.", "SHARMA FOODS PRIVATE LIMITED") == "same"
    assert name_match("Sharma Foods", "Sharma Foods Private Limited") == "suffix"
    assert name_match("Sharma Foods", "Sharma Traders Private Limited") == "different"


def test_address_containment_is_not_a_conflict():
    from app.crm_form import _differs
    assert not _differs("address", "12 Mahatma Gandhi Marg, Navi Mumbai - 400703", "12 Mahatma Gandhi Marg, Navi Mumbai - 400703, Maharashtra")
    assert _differs("address", "12 Mahatma Gandhi Marg, Navi Mumbai - 400703", "12 MG Road, Mumbai - 400001, Maharashtra")
