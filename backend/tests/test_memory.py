"""Memory layer tests with a fake MemoryStore: no network. Covers happy path, outage, and 'never blocks'."""
import json
from pathlib import Path

import httpx
import pytest
from sqlmodel import Session

from app import memory, memory_service
from app.db import engine
from app.memory.base import AddResult, CognifyResult, MemoryUnavailable, SearchResult
from app.memory.cognee_cloud import CogneeCloudStore
from app.models import Case, Document
from app.sarvam.normalise import locate_boxes, to_fields
from app.sarvam.schemas import SCHEMAS

FX = Path(__file__).parent / "fixtures"


class FakeStore:
    name = "fake"

    def __init__(self, fail=False):
        self.fail, self.added, self.cognified = fail, [], []

    def _guard(self):
        if self.fail:
            raise MemoryUnavailable("Cognee Cloud ConnectTimeout: no response in time")

    def add_document(self, dataset, *, file_path, filename, mime, summary_text):
        self._guard()
        self.added.append((dataset, filename, summary_text))
        return AddResult("ds-1", [f"data-{len(self.added)}"])

    def cognify(self, dataset, dataset_id=None, wait=True):
        self._guard()
        self.cognified.append(dataset)
        return CognifyResult("completed", "run-1", "DATASET_PROCESSING_COMPLETED")

    def search(self, dataset, query, search_type="GRAPH_COMPLETION", top_k=15):
        self._guard()
        return SearchResult("Rakesh Sharma holds 18% indirectly.\\n\\nEvidence:\\n- chunk (data_id: data-1)", ["data-1"])

    def health(self):
        return {"available": not self.fail, "mode": "fake"}


@pytest.fixture
def case_with_doc(client):
    """A Sharma-like case document with real extracted fields, created straight in the DB."""
    ex = json.loads((FX / "Shareholding_Declaration.extract.json").read_text(encoding="utf-8"))
    dg = json.loads((FX / "Shareholding_Declaration.digitise.json").read_text(encoding="utf-8"))
    fields = locate_boxes(to_fields(ex, SCHEMAS["shareholding"]), dg)
    doc_id = f"mem_{id(fields)}"
    with Session(engine) as s:
        s.add(Document(id=doc_id, case_id="KYB-20817", doc_type="shareholding", filename="Shareholding.pdf", path=__file__,
                       mime="application/pdf", size_bytes=1, sha256="a" * 64, status="extracted", fields=fields,
                       checks=[{"id": "t", "label": "Direct shareholding adds up to 100%", "status": "pass", "detail": "total 100%"}]))
        s.commit()
    yield doc_id
    memory.set_store(None)


def test_summary_spells_out_the_facts(case_with_doc):
    with Session(engine) as s:
        text = memory_service.document_summary(s.get(Document, case_with_doc), s.get(Case, "KYB-20817"))
    assert "Document: Shareholding / Beneficial Owner Declaration" in text and "Rakesh Sharma" in text
    assert "Sharma Holdings LLP" in text and "percentage: 30" in text and "source page 1" in text
    assert "Check 'Direct shareholding adds up to 100%': pass" in text


def test_store_cognify_ask_happy_path(client, case_with_doc):
    fake = FakeStore()
    memory.set_store(fake)
    assert client.post(f"/api/documents/{case_with_doc}/memory").json()["data"]["memory_status"] == "stored"
    d = client.get(f"/api/documents/{case_with_doc}").json()["data"]
    assert d["memory_status"] == "stored" and d["memory_error"] is None
    assert fake.added[0][0] == "case_royal_rajasthan"                      # one dataset per case

    g = client.post("/api/cases/KYB-20817/memory/cognify").json()["data"]
    assert g["graph_status"] == "ready" and fake.cognified == ["case_royal_rajasthan"]
    assert client.get("/api/cases/KYB-20817").json()["data"]["graphStatus"] == "ready"

    a = client.post("/api/cases/KYB-20817/ask", json={"question": "Who owns more than 10%?"}).json()["data"]
    assert "Rakesh Sharma" in a["answer"] and "Evidence" not in a["answer"]
    assert [x["doc_id"] for x in a["sources"]] == [case_with_doc]          # data_id mapped back to our document


def test_cognee_outage_fails_soft_and_blocks_nothing(client, case_with_doc):
    memory.set_store(FakeStore(fail=True))
    r = client.post(f"/api/documents/{case_with_doc}/memory")
    assert r.status_code == 200 and r.json()["data"]["memory_status"] == "failed"
    d = client.get(f"/api/documents/{case_with_doc}").json()["data"]
    assert d["memory_status"] == "failed" and "ConnectTimeout" in d["memory_error"]
    assert d["status"] == "extracted" and d["fields"]                      # extraction result untouched
    assert client.post("/api/cases/KYB-20817/memory/cognify").json()["data"]["graph_status"] in {"failed", "none"}
    ask = client.post("/api/cases/KYB-20817/ask", json={"question": "Who is the signatory? (outage)"})
    assert ask.status_code == 503 and "unavailable" in ask.json()["detail"]
    assert client.get("/api/cases/KYB-20817").status_code == 200           # the case UI still renders
    assert client.get("/api/cases/KYB-20817/crm-form").status_code == 200
    tl = client.get("/api/cases/KYB-20817").json()["data"]["timeline"]
    assert any(t["title"] == "Memory unavailable" for t in tl)


def test_cloud_store_bad_key_and_breaker(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "COGNEE_API_KEY", "")
    with pytest.raises(MemoryUnavailable, match="not configured"):
        CogneeCloudStore().search("ds", "q")

    monkeypatch.setattr(config, "COGNEE_API_KEY", "bad")
    monkeypatch.setattr(config, "COGNEE_BASE_URL", "http://cognee.test")
    store = CogneeCloudStore()
    monkeypatch.setattr(httpx.Client, "request", lambda self, *a, **k: httpx.Response(401, text="no"))
    with pytest.raises(MemoryUnavailable, match="rejected the credentials"):
        store.search("ds", "q")

    calls = []

    def timeout(self, *a, **k):
        calls.append(1)
        raise httpx.ConnectTimeout("slow")

    monkeypatch.setattr(httpx.Client, "request", timeout)
    for _ in range(2):
        with pytest.raises(MemoryUnavailable):
            store.search("ds", "q")
    with pytest.raises(MemoryUnavailable, match="recent failures"):        # breaker open: fails fast, no 3rd network call
        store.search("ds", "q")
    assert len(calls) == 2


def test_cloud_store_parses_search_and_data_ids(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "COGNEE_API_KEY", "k")
    monkeypatch.setattr(config, "COGNEE_BASE_URL", "http://cognee.test")
    body = [{"dataset_id": "d", "search_result": ["Rakesh Sharma (60% × 30% = 18%).\\n\\nEvidence:\\n- (data_id: 06c2e9f0-1a10-4e37-b21e-0f1f49c71919, chunk_id: x)"]}]
    monkeypatch.setattr(httpx.Client, "request", lambda self, *a, **k: httpx.Response(200, json=body))
    res = CogneeCloudStore().search("case_x", "who?")
    assert "18%" in res.answer and res.data_ids == ["06c2e9f0-1a10-4e37-b21e-0f1f49c71919"]


def test_n8n_native_cognee_report_back(client, case_with_doc):
    s = client.get(f"/api/documents/{case_with_doc}/memory-summary").json()["data"]
    assert s["ready"] and s["dataset"] == "case_royal_rajasthan" and "Rakesh Sharma" in s["text"]

    node_output = {"status": "PipelineRunCompleted", "dataset_id": "x",
                   "data_ingestion_info": [{"data_id": "06c2e9f0-1a10-4e37-b21e-0f1f49c71919"}]}
    r = client.post(f"/api/documents/{case_with_doc}/memory/result", json={"status": "stored", "response": node_output})
    assert r.json()["data"]["memory_status"] == "stored"
    with Session(engine) as ss:
        assert ss.get(Document, case_with_doc).memory_data_ids == ["06c2e9f0-1a10-4e37-b21e-0f1f49c71919"]

    r = client.post(f"/api/documents/{case_with_doc}/memory/result", json={"status": "failed", "error": "401 Unauthorized"})
    assert r.json()["data"]["memory_status"] == "failed" and "401" in r.json()["data"]["error"]

    assert client.post("/api/cases/KYB-20817/memory/graph-start").json()["data"]["graph_status"] == "building"
    assert client.post("/api/cases/KYB-20817/memory/graph-result", json={"status": "completed"}).json()["data"]["graph_status"] == "ready"
    assert client.post("/api/cases/KYB-20817/memory/graph-result", json={"status": "failed", "detail": "timeout"}).json()["data"]["graph_status"] == "failed"
    assert client.post("/api/documents/nope/memory/result", json={"status": "stored"}).status_code == 404


def test_graph_result_with_nothing_stored_is_not_ready(client):
    # KYB-20818 never had a document stored in memory: a 'completed' cognify must not claim a usable graph
    r = client.post("/api/cases/KYB-20818/memory/graph-result", json={"status": "completed"}).json()["data"]
    assert r["graph_status"] == "none"


def test_summary_carries_a_unique_file_prefix_and_items_link_documents(client, case_with_doc):
    s = client.get(f"/api/documents/{case_with_doc}/memory-summary").json()["data"]
    assert s["file_prefix"] == f"doc-{case_with_doc}"
    uid = "11111111-2222-4333-8444-555555555555"
    r = client.post("/api/cases/KYB-20817/memory/items", json={"items": [
        {"id": uid, "name": f"doc-{case_with_doc}-1"}, {"id": "not-a-uuid", "name": "x"}, {"id": uid, "name": "call-abc-1"}]})
    assert r.json()["data"] == {"case_id": "KYB-20817", "linked_documents": 1, "items_seen": 3}
    with Session(engine) as ss:
        assert ss.get(Document, case_with_doc).memory_data_ids == [uid]
    assert client.post("/api/cases/NOPE/memory/items", json={"items": []}).status_code == 404
