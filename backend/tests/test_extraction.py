"""Extraction normalisation + service tests. Sarvam is never called: fixtures are real responses
captured with scripts/dump_sarvam_raw.py (synthetic documents)."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.checks.validators import check_document
from app.sarvam import client as sarvam_client
from app.sarvam.normalise import classify_text, digitise_text, locate_boxes, plain, to_fields
from app.sarvam.schemas import SCHEMAS, validate_all

FX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def test_all_schemas_follow_sarvam_rules():
    assert validate_all() == {}
    assert set(SCHEMAS) == {"pan", "gst", "coi", "board_resolution", "bank_cheque", "director_kyc", "shareholding", "fssai"}


def test_gst_fields_confidence_and_boxes():
    fields = to_fields(load("GST_Certificate.extract.json"), SCHEMAS["gst"])
    assert fields["gstin"]["value"] == "27AABCS1429E1Z8" and fields["gstin"]["page"] == 1
    assert fields["gstin"]["confidence"] > 99                       # 0-1 from Sarvam -> percent
    locate_boxes(fields, load("GST_Certificate.digitise.json"))
    g, addr = fields["gstin"]["box"], fields["principal_place_address"]["box"]
    assert fields["gstin"]["box_source"] == "digitise"
    assert all(0 <= g[k] <= 1 for k in "xywh") and g["page"] == 1
    assert addr["y"] > g["y"]                                         # address is lower on the page than GSTIN
    ys = {round(f["box"]["y"], 3) for k, f in fields.items() if k not in {"validity_to"}}
    assert len(ys) == 8                                               # each field got its own line, no collisions


def test_table_fields_are_boxed_at_table_precision_not_faked_rows():
    fields = to_fields(load("Shareholding_Declaration.extract.json"), SCHEMAS["shareholding"])
    assert [r["name"] for r in fields["shareholders"]["value"]] == ["Anil Sharma", "Priya Sharma", "Sharma Holdings LLP"]
    assert fields["entity_partners"]["value"][0]["partner_name"] == "Rakesh Sharma"
    locate_boxes(fields, load("Shareholding_Declaration.digitise.json"))
    assert fields["shareholders"]["box_precision"] == "table"
    assert len({(b["x"], b["y"], b["h"]) for b in fields["shareholders"]["boxes"]}) == 1   # whole table, no interpolation


def test_no_match_means_no_box():
    fields = {"x": {"value": "ZZZ-NOT-ON-THE-PAGE", "page": 1, "confidence": 99, "box": None, "box_source": "none"}}
    locate_boxes(fields, load("GST_Certificate.digitise.json"))
    assert fields["x"]["box"] is None and fields["x"]["box_source"] == "none"


def test_classify_from_ocr_text():
    assert classify_text(digitise_text(load("GST_Certificate.digitise.json")))[0] == "gst"
    assert classify_text(digitise_text(load("Shareholding_Declaration.digitise.json")))[0] == "shareholding"
    assert classify_text("random grocery list")[0] == "unknown"


def test_document_checks():
    case = SimpleNamespace(entity_type="private_limited", legal_name="Sharma Foods Private Limited", pan="AABCS1429E")
    gst = plain(to_fields(load("GST_Certificate.extract.json"), SCHEMAS["gst"]))
    assert all(c["status"] == "pass" for c in check_document("gst", gst, case))
    bad = check_document("gst", {"gstin": "27AAXXX1429E1Z8"}, case)
    assert any(c["status"] == "fail" for c in bad)
    cheque = check_document("bank_cheque", {"ifsc": "HDFC0000128", "account_number": "50200034928174", "account_type": "Savings"}, case)
    assert [c["status"] for c in cheque] == ["pass", "pass", "fail"]
    assert check_document("director_kyc", {"aadhaar_masked": "123412341234"}, case)[0]["status"] == "fail"
    assert check_document("shareholding", {"shareholders": [{"percentage": "40"}, {"percentage": "30"}]}, case)[0]["status"] == "warn"


def test_limiter_blocks_over_limit():
    lim = sarvam_client.SubmitLimiter(2, window=0.4)
    assert lim.acquire() == 0 and lim.acquire() == 0
    assert lim.acquire() > 0.2                                        # third call had to wait for the window


# ---------- service + route with Sarvam mocked ----------
def _upload(client, name, data=b"%PDF-1.4 x"):
    r = client.post("/api/cases/KYB-20814/documents", files=[("files", (name, data, "application/pdf"))])
    return r.json()["data"]["doc_ids"][0]


def test_extract_route_end_to_end(client, monkeypatch):
    from app import extraction
    calls = []

    def fake_extract(path, schema, language="en-IN"):
        calls.append("extract")
        return {"job_id": "j1", "status": "completed", "raw": load("GST_Certificate.extract.json"), "seconds": 1.0}

    def fake_digitise(path, language="en-IN"):
        calls.append("digitise")
        return {"job_id": "j2", "status": "completed", "raw": load("GST_Certificate.digitise.json"), "seconds": 1.0}

    monkeypatch.setattr(extraction.sarvam, "extract", fake_extract)
    monkeypatch.setattr(extraction.sarvam, "digitise", fake_digitise)
    monkeypatch.setattr(extraction.demo_cache, "get", lambda *a: None)
    monkeypatch.setattr(extraction.demo_cache, "put", lambda *a: None)

    doc_id = _upload(client, "reg06_gst.pdf")
    r = client.post(f"/api/documents/{doc_id}/extract")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "extracted" and data["checks_passed"] is True
    d = client.get(f"/api/documents/{doc_id}").json()["data"]
    assert d["fields"]["gstin"]["value"] == "27AABCS1429E1Z8"
    assert d["fields"]["gstin"]["box"] is not None                    # boxes were located by the background task
    assert calls == ["extract", "digitise"]
    tl = client.get("/api/cases/KYB-20814").json()["data"]["timeline"]
    assert any("extracted" in t["title"] for t in tl) and any(t["title"] == "Evidence highlights ready" for t in tl)


def test_extract_failure_marks_document_error_without_breaking_case(client, monkeypatch):
    from app import extraction

    def boom(*a, **k):
        raise RuntimeError("Sarvam extract job x ended with status 'failed'")

    monkeypatch.setattr(extraction.sarvam, "extract", boom)
    monkeypatch.setattr(extraction.demo_cache, "get", lambda *a: None)
    doc_id = _upload(client, "gst_bad.pdf")
    assert client.post(f"/api/documents/{doc_id}/extract").status_code == 502
    d = client.get(f"/api/documents/{doc_id}").json()["data"]
    assert d["status"] == "error" and "failed" in d["error"]
    assert client.get("/api/cases/KYB-20814").status_code == 200       # case UI keeps working


def test_unknown_type_is_classified_by_ocr_then_extracted(client, monkeypatch):
    from app import extraction
    monkeypatch.setattr(extraction.sarvam, "digitise", lambda *a, **k: {"job_id": "d", "status": "completed", "seconds": 1,
                        "raw": load("Shareholding_Declaration.digitise.json")})
    monkeypatch.setattr(extraction.sarvam, "extract", lambda *a, **k: {"job_id": "e", "status": "completed", "seconds": 1,
                        "raw": load("Shareholding_Declaration.extract.json")})
    monkeypatch.setattr(extraction.demo_cache, "get", lambda *a: None)
    monkeypatch.setattr(extraction.demo_cache, "put", lambda *a: None)
    doc_id = _upload(client, "scan0001.pdf")                         # filename gives no hint -> 'unknown'
    assert client.get(f"/api/documents/{doc_id}").json()["data"]["doc_type"] == "unknown"
    assert client.post(f"/api/documents/{doc_id}/extract").status_code == 200
    d = client.get(f"/api/documents/{doc_id}").json()["data"]
    assert d["doc_type"] == "shareholding" and d["fields"]["shareholders"]["box"] is None and d["fields"]["shareholders"]["boxes"]


def test_list_of_strings_field_does_not_crash():
    raw = {"result": {"resolution_signed_by": ["Anil Sharma", "Priya Sharma"]},
           "annotations": {"resolution_signed_by": [{"confidence": 1, "sources": [{"page_num": 1}]},
                                                    {"confidence": 0.99, "sources": [{"page_num": 1}]}]}}
    schema = {"properties": {"resolution_signed_by": {}}}
    f = to_fields(raw, schema)["resolution_signed_by"]
    assert f["value"] == ["Anil Sharma", "Priya Sharma"] and f["confidence"] == 99.0 and "rows" not in f


def test_sarvam_errors_are_described_without_header_dumps():
    from app.extraction import describe_error

    class BadRequestError(Exception):
        status_code = 400
        body = {"error": {"message": "Unable to parse the PDF file", "code": "invalid_file"}}

        def __str__(self):
            return "headers: {'date': 'x', 'content-type': 'application/problem+json', ...}, status_code: 400"

    msg = describe_error(BadRequestError())
    assert msg == "Sarvam rejected the file (HTTP 400): Unable to parse the PDF file" and "headers" not in msg
    assert describe_error(TimeoutError("job x still 'running'")).startswith("TimeoutError: job x")


def test_status_endpoint_accepts_long_n8n_error_text(client):
    doc_id = _upload(client, "gst_long_error.pdf")
    r = client.post(f"/api/documents/{doc_id}/status", json={"status": "error", "message": "n8n: " + "x" * 3000})
    assert r.status_code == 200 and len(r.json()["data"]["error"]) == 500
