import hashlib

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def test_seed_and_list(client):
    r = client.get("/api/cases").json()
    assert r["ok"] and len(r["data"]["items"]) == 5
    hero = next(c for c in r["data"]["items"] if c["id"] == "KYB-20814")
    assert hero["legalName"] == "Sharma Foods Private Limited"
    assert r["data"]["kpis"]["totalOpen"] == 5


def test_batch_upload_returns_202_with_hashes(client):
    files = [
        ("files", ("GST_Certificate.pdf", PDF, "application/pdf")),
        ("files", ("Company_PAN.pdf", PDF + b"x", "application/pdf")),
        ("files", ("cancelled_cheque.png", b"\x89PNG\r\n\x1a\nfake", "image/png")),
        ("files", ("notes.exe", b"MZ", "application/octet-stream")),
    ]
    r = client.post("/api/cases/KYB-20814/documents", files=files, data={"slot": "tax_gst"})
    assert r.status_code == 202
    data = r.json()["data"]
    assert len(data["doc_ids"]) == 3
    assert [d["filename"] for d in data["rejected"]] == ["notes.exe"]
    by_name = {d["filename"]: d for d in data["documents"]}
    assert by_name["GST_Certificate.pdf"]["doc_type"] == "gst"
    assert by_name["Company_PAN.pdf"]["doc_type"] == "pan"
    assert by_name["cancelled_cheque.png"]["doc_type"] == "bank_cheque"
    assert by_name["GST_Certificate.pdf"]["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert all(d["status"] == "received" and d["memory_status"] == "pending" for d in data["documents"])


def test_file_is_served_back_inline(client):
    docs = client.get("/api/cases/KYB-20814/documents").json()["data"]
    d = next(x for x in docs if x["filename"] == "GST_Certificate.pdf")
    r = client.get(d["file_url"])
    assert r.status_code == 200 and r.content == PDF
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.headers["content-disposition"].startswith("inline")


def test_case_detail_checklist_timeline_and_status(client):
    c = client.get("/api/cases/KYB-20814").json()["data"]
    uploaded = {i["doc_type"] for i in c["uploaded"]}
    assert {"gst", "pan", "bank_cheque"} <= uploaded
    assert "coi" in {i["doc_type"] for i in c["missing"]} and "fssai" in {i["doc_type"] for i in c["missing"]}
    assert c["status"] in {"ready_for_review", "awaiting_merchant", "needs_attention"}
    assert any(t["title"] == "Document uploaded" for t in c["timeline"])
    assert [s["status"] for s in c["stages"]].count("current") == 1

    doc_id = c["checklist"][0]["doc_id"] or next(i["doc_id"] for i in c["uploaded"])
    r = client.post(f"/api/documents/{doc_id}/status", json={"status": "error", "message": "Sarvam timeout"})
    assert r.json()["data"]["status"] == "error" and r.json()["data"]["error"] == "Sarvam timeout"


def test_oversize_and_empty_rejected(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 10)
    r = client.post("/api/cases/KYB-20815/documents",
                    files=[("files", ("big.pdf", b"0123456789ABC", "application/pdf")),
                           ("files", ("empty.pdf", b"", "application/pdf"))])
    assert r.status_code == 202
    assert r.json()["data"]["doc_ids"] == []
    assert len(r.json()["data"]["rejected"]) == 2


def test_action_appends_audit_event(client):
    r = client.post("/api/cases/KYB-20814/action", json={"action": "voice", "channel": "voice"})
    assert r.json()["data"]["status"] == "awaiting_merchant"
    titles = [t["title"] for t in r.json()["data"]["timeline"]]
    assert "Voice chase requested" in titles[-2:]          # followed by the n8n hand-off (or "not placed")
    assert client.post("/api/cases/KYB-20814/actions", json={"action": "request"}).status_code == 200


def test_unknown_case_404(client):
    assert client.get("/api/cases/NOPE").status_code == 404


def test_seeded_demo_cases_have_a_coherent_checklist(client):
    auto = client.get("/api/cases/KYB-20818").json()["data"]               # seeded AUTO: nothing missing
    assert auto["route"] == "AUTO" and auto["missing"] == [] and len(auto["uploaded"]) == 7 and auto["completion"] == 100
    assert all(i["doc_id"] is None for i in auto["uploaded"])               # no files behind seeded entries
    asking = client.get("/api/cases/KYB-20817").json()["data"]              # seeded ASK: one document missing
    assert [m["doc_type"] for m in asking["missing"]] == ["director_kyc"]
    rows = {r["id"]: r for r in client.get("/api/cases").json()["data"]["items"]}
    assert rows["KYB-20818"]["docProgress"] == {"uploaded": 7, "required": 7, "processed": 7}
    assert rows["KYB-20817"]["docProgress"]["uploaded"] == rows["KYB-20817"]["docProgress"]["required"] - 1


def test_only_people_can_decide_and_stages_are_enforced(client):
    # the agent (and the merchant) can never approve, submit or send back
    for actor in ("agent", "merchant"):
        for action in ("approve", "submit_to_compliance", "send_back", "compliance_approve"):
            r = client.post("/api/cases/KYB-20816/action", json={"action": action, "actor": actor})
            assert r.status_code == 403 and "cannot approve or reject anything" in r.json()["detail"], (actor, action)
    # a KAM cannot use the checker's actions and vice versa
    assert client.post("/api/cases/KYB-20816/action", json={"action": "compliance_approve", "actor": "kam"}).status_code == 403
    assert client.post("/api/cases/KYB-20816/action", json={"action": "approve", "actor": "compliance"}).status_code == 403
    # chasing is not a decision: the agent may do it
    assert client.post("/api/cases/KYB-20816/action", json={"action": "request", "actor": "agent"}).status_code == 200

    # the checker cannot act before the KAM has submitted; the KAM cannot approve before verification finished
    assert client.post("/api/cases/KYB-20816/action", json={"action": "compliance_approve", "actor": "compliance"}).status_code == 409
    assert client.post("/api/cases/KYB-20818/action", json={"action": "approve", "actor": "kam"}).status_code == 200      # seeded AUTO case, stage 4
    assert client.post("/api/cases/KYB-20818/action", json={"action": "approve", "actor": "kam"}).status_code == 409      # already submitted
    r = client.post("/api/cases/KYB-20818/action", json={"action": "compliance_approve", "actor": "compliance"})
    assert r.status_code == 200 and r.json()["data"]["stage"] == 6
    titles = [t["title"] for t in r.json()["data"]["timeline"]]
    assert titles[-2:] == ["KAM approved & submitted to Compliance", "Compliance approved"]
    # the refused attempts left no trace on the timeline of the case they targeted
    assert "KAM approved & submitted to Compliance" not in [t["title"] for t in client.get("/api/cases/KYB-20816").json()["data"]["timeline"]]


def test_case_without_verification_cannot_be_approved(client):
    r = client.post("/api/cases/KYB-20815/action", json={"action": "approve", "actor": "kam"})     # seeded, no checks yet
    assert r.status_code == 409 and "has not finished" in r.json()["detail"]
