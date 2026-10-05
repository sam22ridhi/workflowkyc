"""Demo cases. All data is synthetic. Hero case values follow the product brief (not the old frontend mocks)."""
from datetime import timedelta

from sqlmodel import Session, select

from app.db import audit
from app.models import Case, utcnow

CASES = [
    dict(id="KYB-20814", contact_name="Anil Sharma", contact_phone=None, slug="sharma_foods", merchant_name="Sharma Foods Pvt Ltd",
         legal_name="Sharma Foods Private Limited", entity_type="private_limited", industry="food",
         cin="U56101MH2021PTC123456", pan="AABCS1429E", gstin="27AABCS1429E1Z8",
         registered_address="12 MG Road, Mumbai - 400001, Maharashtra",
         stage=2, status="docs_pending", account_status="Cap reached · ₹50k limit", sla=18),
    dict(id="KYB-20815", contact_name="Kiran Patel", contact_phone=None, slug="bharat_agri", merchant_name="Bharat Agri Logistics",
         legal_name="Bharat Agri Logistics LLP", entity_type="llp", industry="logistics",
         cin="AAB-1234", pan="AAJFB5521K", gstin="24AAJFB5521K1Z2",
         registered_address="Plot 14, GIDC Estate, Vadodara - 390010, Gujarat",
         stage=3, status="ai_verifying", account_status="Live, capped · ₹50k", sla=45),
    dict(id="KYB-20816", contact_name="Neha Rao", contact_phone=None, slug="zenith_tech", merchant_name="Zenith Tech Solutions",
         legal_name="Zenith Technologies Private Limited", entity_type="private_limited", industry="software",
         cin="U72900KA2019PTC128765", pan="AABCZ3310M", gstin="29AABCZ3310M1Z5",
         registered_address="4th Floor, Embassy Tech Square, Bengaluru - 560103, Karnataka",
         stage=4, status="ready_for_review", account_status="Live, capped · ₹50k", sla=12),
    dict(id="KYB-20817", contact_name="Suresh Kumar Saini", contact_phone=None, slug="royal_rajasthan", merchant_name="Royal Rajasthan Spices",
         legal_name="Royal Rajasthan Spices", entity_type="proprietorship", industry="food",
         cin=None, pan="BKQPS7788L", gstin="08BKQPS7788L1ZP",
         registered_address="Johari Bazaar, Jaipur - 302003, Rajasthan",
         stage=2, status="docs_pending", account_status="Live, capped · ₹50k", sla=8),
    dict(id="KYB-20818", contact_name="Arjun Malhotra", contact_phone=None, slug="apex_cloud", merchant_name="Apex Cloud Telecom",
         legal_name="Apex Cloud Telecom Limited", entity_type="public_limited", industry="telecom",
         cin="L64200DL2012PLC241903", pan="AAACA9087D", gstin="07AAACA9087D1Z9",
         registered_address="Tower B, Nehru Place, New Delhi - 110019",
         stage=4, status="ready_for_review", account_status="Live, capped · ₹50k", sla=52),
]


def seed_if_empty(session: Session) -> int:
    if session.exec(select(Case)).first():
        return 0
    for c in CASES:
        data = dict(c)
        sla = data.pop("sla")
        session.add(Case(**data, sla_due=utcnow() + timedelta(minutes=sla)))
    session.commit()
    for c in CASES:
        audit(session, c["id"], "merchant", "Application submitted",
              "Merchant submitted onboarding details (Stage 1 live, ₹50k cap).", "neutral")
    _seed_precomputed_results(session)
    return len(CASES)


# The four non-hero cases have no documents in the demo. To make the KAM dashboard realistic they get
# PRECOMPUTED check results, clearly marked as seeded. Only Sharma Foods is checked from real documents.
SEEDED_NOTE = "Seeded demo result (synthetic, no documents processed)."
_PRECOMPUTED = {
    # case_id: (route, missing documents, {check_id: (status, action, detail)}); checks not listed pass (or skip if n/a)
    "KYB-20816": ("AUTO", [], {}),
    "KYB-20818": ("AUTO", [], {}),
    "KYB-20817": ("ASK", ["director_kyc"], {
        "required_documents": ("fail", "ask", "Missing for a proprietorship: Director KYC (proprietor's ID proof)."),
        "bank_holder_name": ("fail", "ask", "The bank's penny-drop returned the holder “SURESH KUMAR SAINI”, not the trade "
                                            "name “Royal Rajasthan Spices”; ask for a bank letter linking the account to the business."),
    }),
}


def _seed_precomputed_results(session: Session, only: set[str] | None = None) -> None:
    from app.checks import cross_check as cc   # local import: cross_check imports app.models / app.db
    from app.models import CheckResult
    from app.registry import mock_registry

    seeded_evidence = [{"doc_id": None, "doc_type": None, "field": None, "page": None, "value": None, "source": "Seeded demo data"}]
    for case_id, (route, missing, overrides) in _PRECOMPUTED.items():
        if only is not None and case_id not in only:
            continue
        case = session.get(Case, case_id)
        checks = []
        for c in cc.evaluate(case, [], mock_registry.lookup(case_id)):   # the 10 checks, with their labels
            default = ("skip" if c["status"] == "skip" else "pass", None, SEEDED_NOTE)
            status, action, detail = overrides.get(c["id"], default)
            checks.append({**c, "status": status, "action": action, "detail": detail, "evidence": seeded_evidence})
            session.add(CheckResult(case_id=case_id, check_id=c["id"], label=c["label"], status=status, action=action,
                                    detail=detail, evidence=seeded_evidence))
        case.seed_missing = ",".join(missing)
        case.route, case.summary = route, f"{cc.summarise(checks, route)} ({SEEDED_NOTE})"
        session.add(case)
    session.commit()
