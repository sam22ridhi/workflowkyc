"""The all-correct Sharma Foods set (seed/demo_pack_correct): fed to the checks with the values exactly as printed on it, everything passes.
This verifies the RULES on the correct documents, not Sarvam's reading of them (that needs Sarvam credit: run the set through the app)."""
import pytest
from sqlmodel import Session, select

from app.checks import cross_check
from app.db import engine
from app.models import Case, CheckResult, Document

CASE = "KYB-20814"


def f(**kw):
    return {k: {"value": v, "confidence": 99.0, "page": 1} for k, v in kw.items()}


FIELDS = {
    "pan": [f(pan_number="AABCS1429E", holder_name="SHARMA FOODS PRIVATE LIMITED", date="14/08/2021")],
    "gst": [f(gstin="27AABCS1429E1Z8", legal_name="SHARMA FOODS PRIVATE LIMITED", trade_name="Sharma Foods", constitution_of_business="Private Limited Company",
              principal_place_address="12 Mahatma Gandhi Marg, Navi Mumbai - 400703, Maharashtra")],
    "coi": [f(cin="U56101MH2021PTC123456", company_name="SHARMA FOODS PRIVATE LIMITED", date_of_incorporation="14/08/2021", company_type="Private Limited Company",
              registered_office_address="12 MG Road, Mumbai - 400001, Maharashtra")],
    "board_resolution": [f(company_name="SHARMA FOODS PRIVATE LIMITED", cin="U56101MH2021PTC123456", resolution_date="02/09/2026",
                           authorised_signatory_name="Anil Sharma", authorised_signatory_designation="Director and Authorised Signatory",
                           resolution_signed_by=["Anil Sharma", "Priya Sharma"])],
    "bank_cheque": [f(account_holder_name="SHARMA FOODS PRIVATE LIMITED", account_number="50200034928174", ifsc="HDFC0000128", bank_name="HDFC BANK", account_type="Current")],
    "director_kyc": [f(full_name="Anil Sharma", id_type="Aadhaar (masked)", aadhaar_masked="XXXX XXXX 4821", din="08492019", date_of_birth="09/03/1978"),
                     f(full_name="Priya Sharma", id_type="Aadhaar (masked)", aadhaar_masked="XXXX XXXX 7733", din="08492020", date_of_birth="22/11/1981"),
                     f(full_name="Rakesh Sharma", id_type="Aadhaar (masked)", aadhaar_masked="XXXX XXXX 5590", date_of_birth="03/05/1975"),
                     f(full_name="Meera Sharma", id_type="Aadhaar (masked)", aadhaar_masked="XXXX XXXX 3318", date_of_birth="17/09/1979")],
    "shareholding": [f(company_name="SHARMA FOODS PRIVATE LIMITED", as_of_date="01/09/2026",
                       shareholders=[{"name": "Anil Sharma", "holder_type": "individual", "percentage": "40"},
                                     {"name": "Priya Sharma", "holder_type": "individual", "percentage": "30"},
                                     {"name": "Sharma Holdings LLP", "holder_type": "llp", "percentage": "30"}],
                       entity_partners=[{"entity_name": "Sharma Holdings LLP", "partner_name": "Rakesh Sharma", "percentage": "60"},
                                        {"entity_name": "Sharma Holdings LLP", "partner_name": "Meera Sharma", "percentage": "40"}])],
    "fssai": [f(licence_number="11521999000123", business_name="SHARMA FOODS PRIVATE LIMITED", premises_address="12 Mahatma Gandhi Marg, Navi Mumbai - 400703",
                licence_type="State Licence", kind_of_business="Manufacturer", valid_from="10/10/2025", valid_until="09/10/2030")],
    "electricity_bill": [f(consumer_name="SHARMA FOODS PRIVATE LIMITED", consumer_number="170240055310",
                           service_address="12 Mahatma Gandhi Marg, Navi Mumbai - 400703, Maharashtra", bill_date="05/09/2026")],
}


@pytest.fixture
def hero(client):
    with Session(engine) as s:
        case = s.get(Case, CASE)
        before = (case.operating_address, case.stage, case.status, case.route, case.summary)
        for row in list(s.exec(select(Document).where(Document.case_id == CASE))):
            s.delete(row)
        n = 0
        for doc_type, items in FIELDS.items():
            for fields in items:
                n += 1
                s.add(Document(id=f"cp_{n}", case_id=CASE, doc_type=doc_type, filename=f"{doc_type}_{n}.pdf", path="x", mime="application/pdf", size_bytes=1,
                               sha256=str(n).ljust(64, "0"), status="extracted", fields=fields))
        case.operating_address = None
        s.add(case)
        s.commit()
    yield client
    with Session(engine) as s:
        for row in list(s.exec(select(Document).where(Document.case_id == CASE))):
            s.delete(row)
        for row in list(s.exec(select(CheckResult).where(CheckResult.case_id == CASE))):
            s.delete(row)
        case = s.get(Case, CASE)
        case.operating_address, case.stage, case.status, case.route, case.summary = before
        s.add(case)
        s.commit()


def statuses(client) -> dict:
    return {c["id"]: c["status"] for c in client.get(f"/api/cases/{CASE}").json()["data"]["checks"]}


def test_only_the_application_address_stands_between_the_correct_set_and_a_clean_pass(hero):
    out = cross_check.run(CASE)
    st = {c["id"]: c["status"] for c in out["checks"]}
    # the signatory is a director, every owner has KYC, the cheque has the full legal name: those three planted problems are gone
    assert st["signatory_is_director"] == "pass" and st["beneficial_owners"] == "pass" and st["bank_holder_name"] == "pass"
    # the application still says the business operates at "12 MG Road, Mumbai": the GST certificate, FSSAI licence and electricity bill say Navi Mumbai
    assert st["address_consistent"] == "fail" and out["route"] == "ASK"
    assert [k for k, v in st.items() if v == "fail"] == ["address_consistent"]


def test_the_kam_confirming_the_operating_address_in_the_crm_form_clears_it_and_the_case_is_auto(hero):
    r = hero.post(f"/api/cases/{CASE}/crm-form/override", json={"key": "principal_address", "value": "12 Mahatma Gandhi Marg, Navi Mumbai - 400703, Maharashtra",
                                                                "note": "confirmed with the merchant by phone"})
    assert r.status_code == 200
    st = statuses(hero)
    assert all(v in {"pass", "skip"} for v in st.values()), {k: v for k, v in st.items() if v not in {"pass", "skip"}}
    d = hero.get(f"/api/cases/{CASE}").json()["data"]
    assert d["route"] == "AUTO" and d["status"] == "ready_for_review"
    assert "Application operating address updated" in [t["title"] for t in d["timeline"]]


def test_the_registered_office_may_differ_from_the_principal_place(hero):
    """The certificate of incorporation says Mumbai (registered office) while GST, FSSAI and the bill say Navi Mumbai (where it operates): that is not drift."""
    hero.post(f"/api/cases/{CASE}/crm-form/override", json={"key": "principal_address", "value": "12 Mahatma Gandhi Marg, Navi Mumbai - 400703, Maharashtra"})
    chk = next(c for c in hero.get(f"/api/cases/{CASE}").json()["data"]["checks"] if c["id"] == "address_consistent")
    assert chk["status"] == "pass" and "agree" in chk["detail"]
