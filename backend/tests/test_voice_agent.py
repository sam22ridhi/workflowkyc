"""Voice Chase: agent context from live checks, escalations held back, outcomes recorded, n8n hand-off."""
import copy

import httpx
import pytest
from sqlmodel import Session, select

from app import config
from app.db import engine
from app.models import Case, CheckResult, Document
from tests.test_cross_check import hero_docs


@pytest.fixture
def hero_checked(client):
    with Session(engine) as s:
        for d in hero_docs():
            s.add(Document(id=f"va_{d.id}", case_id="KYB-20814", doc_type=d.doc_type, filename=d.filename, path="x",
                           mime="application/pdf", size_bytes=1, sha256="0" * 64, status="extracted", fields=copy.deepcopy(d.fields)))
        s.commit()
    client.post("/api/cases/KYB-20814/cross-check")
    yield
    with Session(engine) as s:
        for row in list(s.exec(select(Document).where(Document.id.like("va_%")))) + list(s.exec(select(CheckResult).where(CheckResult.case_id == "KYB-20814"))):
            s.delete(row)
        case = s.get(Case, "KYB-20814")
        case.route, case.summary, case.status, case.stage = None, None, "docs_pending", 2
        s.add(case)
        s.commit()


def test_context_has_only_merchant_fixable_items(client, hero_checked):
    ctx = client.get("/api/cases/KYB-20814/voice-chase/context").json()["data"]
    v = ctx["agent_variables"]
    assert ctx["should_call"] and v["issue_count"] == "2" and v["contact_name"] == "Anil Sharma"
    assert "cancelled cheque" in v["issues_en"] and "GST certificate" in v["issues_en"]
    assert "कैंसल्ड चेक" in v["issues_hi"] and "जीएसटी" in v["issues_hi"]
    assert v["documents_needed_en"].startswith("1. a cancelled cheque or bank letter")
    # escalations never reach the agent
    assert "Ravish" not in str(v) and "Rakesh" not in str(v) and "director" not in v["issues_en"]
    assert set(ctx["held_back_for_kam"]) == {"Board-resolution signatory is a current director", "Beneficial owners above 10% identified and KYC'd"}
    assert ctx["initial_bot_message"].startswith("नमस्ते Anil Sharma") and "2 छोटी बातें" in ctx["initial_bot_message"]
    assert all(isinstance(x, str) for x in v.values())


def test_context_lists_missing_documents_and_nothing_to_call_about(client):
    asking = client.get("/api/cases/KYB-20817/voice-chase/context").json()["data"]     # seeded ASK case
    assert asking["should_call"] and "Director KYC" in asking["agent_variables"]["documents_needed_en"]
    auto = client.get("/api/cases/KYB-20818/voice-chase/context").json()["data"]       # seeded AUTO case
    assert not auto["should_call"] and auto["agent_variables"]["issues_en"] == "none"


def test_result_goes_to_timeline(client):
    r = client.post("/api/cases/KYB-20817/voice-chase/result", json={
        "outcome": "promised_upload", "summary": "Will upload proprietor ID by tomorrow.",
        "transcript": [{"role": "bot", "text": "नमस्ते"}, {"role": "user", "text": "हाँ, कल भेज दूँगा"}], "call_id": "c-1"})
    assert r.json()["data"]["title"] == "Voice call: merchant will upload"
    last = client.get("/api/cases/KYB-20817").json()["data"]["timeline"][-1]
    assert last["title"] == "Voice call: merchant will upload" and "कल भेज दूँगा" in last["detail"] and "c-1" in last["detail"]
    assert client.post("/api/cases/KYB-20817/voice-chase/result", json={"outcome": "teleported"}).status_code == 422


def test_voice_action_is_honest_without_phone_setup(client, monkeypatch):
    monkeypatch.setattr(config, "N8N_VOICE_WEBHOOK_URL", "")
    tl = client.post("/api/cases/KYB-20817/action", json={"action": "voice", "channel": "voice", "phone": "+919812345678"}).json()["data"]["timeline"]
    assert [t["title"] for t in tl[-2:]] == ["Voice chase requested", "Voice call not placed"]
    assert "not configured" in tl[-1]["detail"]


def test_voice_action_hands_off_to_n8n(client, monkeypatch):
    sent = {}

    def fake_post(url, json, timeout):
        sent.update(url=url, json=json)
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(config, "N8N_VOICE_WEBHOOK_URL", "http://n8n.test/webhook/karyakarta-voice-chase")
    monkeypatch.setattr(httpx, "post", fake_post)
    tl = client.post("/api/cases/KYB-20817/action", json={"action": "voice", "channel": "voice", "phone": "+919812345678"}).json()["data"]["timeline"]
    assert sent["json"] == {"case_id": "KYB-20817", "to_number": "+919812345678"} and tl[-1]["title"] == "Voice chase handed to n8n"
    # WhatsApp / email do not trigger the voice workflow
    sent.clear()
    client.post("/api/cases/KYB-20817/action", json={"action": "voice", "channel": "whatsapp"})
    assert sent == {}


def test_call_result_is_stored_and_shown_on_the_case(client):
    r = client.post("/api/cases/KYB-20817/voice-chase/result", json={
        "outcome": "promised_upload", "summary": "TEST: will upload the proprietor ID tomorrow evening.",
        "transcript": [{"role": "agent", "text": "नमस्ते Suresh जी"}, {"role": "merchant", "text": "कल शाम तक भेज दूँगा"}], "call_id": "sv-1"})
    data = r.json()["data"]
    assert data["worth_remembering"] and len(data["voice_call_id"]) == 12
    calls = client.get("/api/cases/KYB-20817").json()["data"]["voiceCalls"]
    mine = next(c for c in calls if c["id"] == data["voice_call_id"])
    assert mine["title"] == "Voice call: merchant will upload" and mine["memoryStatus"] == "pending" and mine["callId"] == "sv-1"
    assert mine["transcript"][1] == {"role": "merchant", "text": "कल शाम तक भेज दूँगा"}


def test_not_placed_results_are_not_sent_to_memory(client):
    d = client.post("/api/cases/KYB-20817/voice-chase/result", json={"outcome": "not_configured", "summary": "x"}).json()["data"]
    assert not d["worth_remembering"]
    call = next(c for c in client.get("/api/cases/KYB-20817").json()["data"]["voiceCalls"] if c["id"] == d["voice_call_id"])
    assert call["memoryStatus"] == "n/a"


def test_call_memory_summary_and_report_back(client):
    d = client.post("/api/cases/KYB-20817/voice-chase/result", json={
        "outcome": "callback_requested", "summary": "TEST: asked to be called after 6 pm.",
        "transcript": [{"role": "merchant", "text": "शाम को बात करें"}]}).json()["data"]
    s = client.get(f"/api/voice-calls/{d['voice_call_id']}/memory-summary").json()["data"]
    assert s["dataset"] == "case_royal_rajasthan" and "Royal Rajasthan Spices" in s["text"] and "after 6 pm" in s["text"] and "- merchant: शाम को बात करें" in s["text"]
    assert client.post(f"/api/voice-calls/{d['voice_call_id']}/memory/result", json={"status": "stored"}).json()["data"]["memory_status"] == "stored"
    assert client.post(f"/api/voice-calls/{d['voice_call_id']}/memory/result", json={"status": "failed", "error": "401"}).json()["data"]["memory_status"] == "failed"
    titles = [t["title"] for t in client.get("/api/cases/KYB-20817").json()["data"]["timeline"]]
    assert "Voice call stored in Cognee memory" in titles and "Memory unavailable" in titles
    assert client.get("/api/voice-calls/nope/memory-summary").status_code == 404
    assert client.post("/api/voice-calls/nope/memory/result", json={"status": "stored"}).status_code == 404


def test_graph_is_ready_when_only_a_voice_call_is_stored(client):
    d = client.post("/api/cases/KYB-20818/voice-chase/result", json={"outcome": "reached", "summary": "TEST: spoke briefly."}).json()["data"]
    assert client.post("/api/cases/KYB-20818/memory/graph-result", json={"status": "completed"}).json()["data"]["graph_status"] == "none"   # nothing stored yet
    client.post(f"/api/voice-calls/{d['voice_call_id']}/memory/result", json={"status": "stored"})
    assert client.post("/api/cases/KYB-20818/memory/graph-result", json={"status": "completed"}).json()["data"]["graph_status"] == "ready"
