"""End to end on the 8 real Sharma Foods PDFs: upload -> extract -> memory -> graph -> cross-check -> boxes.

Sarvam is mocked with its RECORDED responses (demo_cache/, keyed by file SHA-256); Cognee is a fake store.
No network. Asserts the acceptance criteria: all four planted issues found with evidence, route ESCALATE,
memory stored, case Q&A answered with sources, CRM form populated with conflicts.
"""
import hashlib
import json
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app import extraction, memory, orchestrator
from app.db import engine
from app.models import Case, CheckResult, CrmOverride, Document
from tests.test_memory import FakeStore

BACKEND = Path(__file__).resolve().parent.parent
PDFS = sorted((BACKEND / "seed" / "sharma_foods").glob("*.pdf"))
CACHE = BACKEND / "demo_cache"


def _recorded(path: str, kind: str) -> dict:
    sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    f = CACHE / f"{sha}.{kind}.json"
    if not f.exists():
        pytest.skip(f"no recorded Sarvam response for {Path(path).name}; run seed.bat --refresh-cache")
    return {"job_id": "recorded", "status": "completed", "raw": json.loads(f.read_text(encoding="utf-8")), "seconds": 0.0}


@pytest.fixture
def hero_pipeline(client, monkeypatch):
    calls = []

    def fake_extract(path, schema, language="en-IN"):
        doc_type = next(t for t, s in extraction.SCHEMAS.items() if s is schema)
        calls.append(("extract", doc_type))
        return _recorded(path, f"extract-{doc_type}")

    def fake_digitise(path, language="en-IN"):
        calls.append(("digitise", Path(path).name))
        return _recorded(path, "digitise")

    monkeypatch.setattr(extraction.sarvam, "extract", fake_extract)
    monkeypatch.setattr(extraction.sarvam, "digitise", fake_digitise)
    monkeypatch.setattr(extraction.demo_cache, "get", lambda *a: None)      # force the (mocked) live path
    monkeypatch.setattr(extraction.demo_cache, "put", lambda *a: None)
    store = FakeStore()
    memory.set_store(store)

    files = [("files", (p.name, p.read_bytes(), "application/pdf")) for p in PDFS]
    r = client.post("/api/cases/KYB-20814/documents", files=files)
    assert r.status_code == 202
    ids = r.json()["data"]["doc_ids"]
    orchestrator.run_batch("KYB-20814", ids)
    yield {"ids": ids, "calls": calls, "store": store}

    memory.set_store(None)
    with Session(engine) as s:   # leave the shared test DB as other tests expect it
        for row in (list(s.exec(select(Document).where(Document.id.in_(ids))))
                    + list(s.exec(select(CheckResult).where(CheckResult.case_id == "KYB-20814")))
                    + list(s.exec(select(CrmOverride).where(CrmOverride.case_id == "KYB-20814")))):
            s.delete(row)
        case = s.get(Case, "KYB-20814")
        case.route, case.summary, case.status, case.stage, case.graph_status = None, None, "docs_pending", 2, "none"
        s.add(case)
        s.commit()


def test_hero_case_end_to_end(client, hero_pipeline):
    assert len(PDFS) == 8
    ids = set(hero_pipeline["ids"])
    docs = [d for d in client.get("/api/cases/KYB-20814/documents").json()["data"] if d["doc_id"] in ids]   # other tests share this case
    assert len(docs) == 8
    assert {d["doc_type"] for d in docs} == {"pan", "gst", "coi", "board_resolution", "bank_cheque", "director_kyc", "shareholding", "fssai"}
    assert all(d["status"] == "extracted" for d in docs)
    assert all(d["memory_status"] == "stored" for d in docs)
    assert all(any(f.get("box") or f.get("boxes") for f in d["fields"].values()) for d in docs)   # evidence boxes everywhere
    assert sum(1 for c in hero_pipeline["calls"] if c[0] == "extract") == 8
    assert sum(1 for c in hero_pipeline["calls"] if c[0] == "digitise") == 8

    case = client.get("/api/cases/KYB-20814").json()["data"]
    assert case["route"] == "ESCALATE" and case["graphStatus"] == "ready" and case["stage"] == 4
    failed = {c["id"]: c for c in case["checks"] if c["status"] == "fail"}
    assert set(failed) == {"bank_holder_name", "signatory_is_director", "beneficial_owners", "address_consistent"}
    assert "Ravish Sahay" in failed["signatory_is_director"]["detail"]
    assert "Rakesh Sharma 18% effective" in failed["beneficial_owners"]["detail"]
    assert "Navi Mumbai" in failed["address_consistent"]["detail"]
    assert "“Sharma Foods”" in failed["bank_holder_name"]["detail"]
    for c in failed.values():   # every finding points at a real document page
        assert any(e["doc_id"] in hero_pipeline["ids"] and e["page"] == 1 for e in c["evidence"])

    crm = client.get("/api/cases/KYB-20814/crm-form").json()["data"]
    fields = {f["key"]: f for s in crm["sections"] for f in s["fields"]}
    assert crm["summary"]["fill_percent"] == 100 and crm["summary"]["conflicts"] == 2
    assert fields["bank_holder"]["status"] == "conflict" and fields["principal_address"]["status"] == "conflict"
    assert fields["gstin"]["value"] == "27AABCS1429E1Z8" and fields["gstin"]["source"] == "Source: GST Cert p.1"

    store = hero_pipeline["store"]
    assert len(store.added) == 8 and store.cognified == ["case_sharma_foods"]
    a = client.post("/api/cases/KYB-20814/ask", json={"question": "Who owns more than 10%? (integration)"}).json()["data"]
    assert "Rakesh Sharma" in a["answer"] and len(a["sources"]) == 1

    titles = [t["title"] for t in case["timeline"]]
    order = ["Document uploaded", "Extraction started", "Stored in Cognee memory", "Knowledge graph ready",
             "Cross-check complete · route ESCALATE", "Evidence highlights ready"]
    positions = [len(titles) - 1 - titles[::-1].index(t) for t in order]   # last occurrence = this run (shared timeline)
    assert positions == sorted(positions), titles
