"""KAM housekeeping: deleting a submitted file, and resetting a demo case so the story can be shown again."""
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app import config, memory
from app.db import engine
from app.memory.base import MemoryUnavailable
from app.models import AuditEvent, Case, CheckResult, Document, VoiceCall

CASE = "KYB-20815"


class Store:
    name = "fake"

    def __init__(self, fail=False):
        self.fail, self.deleted, self.datasets_deleted = fail, [], []

    def delete_data(self, dataset, data_ids):
        if self.fail:
            raise MemoryUnavailable("Cognee down")
        self.deleted.append((dataset, list(data_ids)))
        return len(data_ids)

    def delete_dataset(self, dataset):
        if self.fail:
            raise MemoryUnavailable("Cognee down")
        self.datasets_deleted.append(dataset)
        return True


def _make_doc(s: Session, name: str, doc_type: str, memory_ids=None) -> Document:
    folder = Path(config.STORAGE_DIR) / CASE
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / name
    f.write_bytes(b"%PDF-1.4 " + name.encode())
    d = Document(id=f"adm_{name}", case_id=CASE, doc_type=doc_type, filename=name, path=str(f), mime="application/pdf", size_bytes=10,
                 sha256=name.ljust(64, "0"), status="extracted", fields={}, memory_status="stored" if memory_ids else "pending", memory_data_ids=memory_ids)
    s.add(d)
    return d


@pytest.fixture
def case(client, monkeypatch):
    monkeypatch.setattr(config, "CPV_ALLOW_DEMO_REFERENCE", True)
    store = Store()
    memory.set_store(store)
    with Session(engine) as s:
        _wipe(s)
        c = s.get(Case, CASE)
        c.stage, c.status, c.route = 4, "ready_for_review", "ASK"
        s.add(c)
        _make_doc(s, "GST.pdf", "gst", ["data-1", "data-2"])
        _make_doc(s, "PAN.pdf", "pan")
        s.commit()
    yield {"client": client, "store": store}
    memory.set_store(None)
    with Session(engine) as s:
        _wipe(s)
        c = s.get(Case, CASE)                                   # leave the seeded case as other tests expect it
        c.stage, c.status, c.route, c.summary, c.graph_status = 3, "ai_verifying", None, None, "none"
        s.add(c)
        for row in list(s.exec(select(CheckResult).where(CheckResult.case_id == CASE))):
            s.delete(row)
        s.commit()


def _wipe(s: Session) -> None:
    for row in list(s.exec(select(Document).where(Document.case_id == CASE))):
        s.delete(row)
    s.commit()


def titles(s: Session) -> list[str]:
    return [e.action for e in s.exec(select(AuditEvent).where(AuditEvent.case_id == CASE).order_by(AuditEvent.id))]


def test_only_the_kam_can_delete_a_file(case):
    c = case["client"]
    for actor in ("agent", "compliance", "merchant"):
        r = c.delete(f"/api/documents/adm_GST.pdf?actor={actor}")
        assert r.status_code == 403 and "Only the KAM" in r.json()["detail"]
    with Session(engine) as s:
        assert s.get(Document, "adm_GST.pdf") is not None


def test_deleting_removes_the_file_forgets_it_in_memory_and_reruns_the_checks(case):
    r = case["client"].delete("/api/documents/adm_GST.pdf?actor=kam")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["deleted"] == "GST.pdf" and d["remaining"] == 1 and "re-run" in d["outcome"] and "Removed 2 item(s)" in d["memory"]
    assert case["store"].deleted == [("case_bharat_agri", ["data-1", "data-2"])]
    assert not (Path(config.STORAGE_DIR) / CASE / "GST.pdf").exists() and (Path(config.STORAGE_DIR) / CASE / "PAN.pdf").exists()
    with Session(engine) as s:
        assert s.get(Document, "adm_GST.pdf") is None and s.get(Document, "adm_PAN.pdf") is not None
        t = titles(s)
        assert "Document deleted by the KAM" in t and any(x.startswith("Cross-check complete") for x in t)
        assert s.exec(select(CheckResult).where(CheckResult.case_id == CASE)).first() is not None


def test_deleting_the_last_file_sends_the_case_back_to_documents_pending(case):
    c = case["client"]
    c.delete("/api/documents/adm_GST.pdf?actor=kam")
    r = c.delete("/api/documents/adm_PAN.pdf?actor=kam").json()["data"]
    assert r["remaining"] == 0 and "documents pending" in r["outcome"]
    detail = c.get(f"/api/cases/{CASE}").json()["data"]
    assert detail["stage"] == 2 and detail["route"] is None and detail["checks"] == [] and detail["graphStatus"] == "none"
    assert detail["status"] == "awaiting_merchant"                                    # docs_pending is shown as awaiting the merchant


def test_a_submitted_case_keeps_its_files(case):
    with Session(engine) as s:
        c = s.get(Case, CASE)
        c.stage = 5
        s.add(c)
        s.commit()
    r = case["client"].delete("/api/documents/adm_GST.pdf?actor=kam")
    assert r.status_code == 409 and "already been submitted to Compliance" in r.json()["detail"]
    with Session(engine) as s:
        c = s.get(Case, CASE)
        c.stage = 4
        s.add(c)
        s.commit()


def test_cognee_being_down_does_not_stop_the_delete_and_is_said_on_the_timeline(case):
    memory.set_store(Store(fail=True))
    r = case["client"].delete("/api/documents/adm_GST.pdf?actor=kam")
    assert r.status_code == 200 and "Could not remove it from the merchant twin" in r.json()["data"]["memory"]
    with Session(engine) as s:
        assert s.get(Document, "adm_GST.pdf") is None
        ev = s.exec(select(AuditEvent).where(AuditEvent.case_id == CASE, AuditEvent.action == "Document deleted by the KAM").order_by(AuditEvent.id.desc())).first()
        assert "Cognee down" in ev.detail


def test_an_unlinked_memory_copy_is_reported_not_guessed(case):
    with Session(engine) as s:
        d = s.get(Document, "adm_PAN.pdf")
        d.memory_status, d.memory_data_ids = "stored", None
        s.add(d)
        s.commit()
    r = case["client"].delete("/api/documents/adm_PAN.pdf?actor=kam").json()["data"]
    assert "could not be matched" in r["memory"] and case["store"].deleted == []


def test_demo_reset_is_off_unless_enabled(case, monkeypatch):
    monkeypatch.setattr(config, "CPV_ALLOW_DEMO_REFERENCE", False)
    r = case["client"].post(f"/api/cases/{CASE}/demo/reset")
    assert r.status_code == 403 and "disabled" in r.json()["detail"]


def test_demo_reset_puts_the_case_back_to_its_start_and_clears_memory(case):
    with Session(engine) as s:
        s.add(VoiceCall(id="adm_call", case_id=CASE, outcome="reached", summary="x", transcript=[]))
        s.commit()
    r = case["client"].post(f"/api/cases/{CASE}/demo/reset")
    assert r.status_code == 200 and "deleted" in r.json()["data"]["memory"]
    assert case["store"].datasets_deleted == ["case_bharat_agri"]
    with Session(engine) as s:
        assert not list(s.exec(select(Document).where(Document.case_id == CASE)))
        assert not list(s.exec(select(VoiceCall).where(VoiceCall.case_id == CASE)))
        c = s.get(Case, CASE)
        assert (c.stage, c.status, c.route, c.graph_status) == (3, "ai_verifying", None, "none")
        assert titles(s) == ["Application submitted", "Demo reset"]
    assert not (Path(config.STORAGE_DIR) / CASE).exists()


def test_reset_restores_the_seeded_checks_of_a_seeded_case(case):
    r = case["client"].post("/api/cases/KYB-20817/demo/reset")
    assert r.status_code == 200
    with Session(engine) as s:
        checks = list(s.exec(select(CheckResult).where(CheckResult.case_id == "KYB-20817")))
        assert len(checks) == 10 and any(c.status == "fail" for c in checks)
        assert s.get(Case, "KYB-20817").route == "ASK"


def test_only_seeded_onboarding_cases_can_be_reset(case):
    assert case["client"].post("/api/cases/KYB-NOPE/demo/reset").status_code == 404
    with Session(engine) as s:
        s.add(Case(id="KYB-ODD", slug="odd", merchant_name="Odd", legal_name="Odd", entity_type="proprietorship"))
        s.commit()
    try:
        assert case["client"].post("/api/cases/KYB-ODD/demo/reset").status_code == 409
    finally:
        with Session(engine) as s:
            s.delete(s.get(Case, "KYB-ODD"))
            s.commit()
