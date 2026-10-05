"""V-CIP preparation: randomized Hindi liveness questions, the pre-interview call by a second agent, and the human sign-off."""
import random
from datetime import datetime, timezone

import httpx
import pytest
from sqlmodel import Session, select

from app import config, vcip
from app.db import engine
from app.models import AuditEvent, Case, VcipRecord

CASE = "KYB-20816"


def resp(status, body):
    return httpx.Response(status, json=body, request=httpx.Request("POST", "https://x.test"))


@pytest.fixture
def at_vcip(client, monkeypatch):
    monkeypatch.setattr(config, "N8N_VOICE_WEBHOOK_URL", "")
    with Session(engine) as s:
        for row in list(s.exec(select(VcipRecord).where(VcipRecord.case_id == CASE))) + list(
                s.exec(select(AuditEvent).where(AuditEvent.case_id == CASE, AuditEvent.action == "Voice call placed"))):   # earlier tests' markers
            s.delete(row)
        case = s.get(Case, CASE)
        case.stage, case.status, case.contact_name = 7, "ready_for_review", "Neha Rao"
        s.add(case)
        s.commit()
    yield client
    with Session(engine) as s:
        for row in s.exec(select(VcipRecord).where(VcipRecord.case_id == CASE)):
            s.delete(row)
        case = s.get(Case, CASE)
        case.stage, case.status = 4, "ready_for_review"
        s.add(case)
        s.commit()


# ---------------------------------------------------------------- the questions
def test_questions_are_random_correct_and_always_include_a_number_to_repeat():
    case = Case(id="X", slug="x", merchant_name="Royal", legal_name="Royal Rajasthan Spices", entity_type="proprietorship", contact_name="Suresh Kumar Saini")
    wednesday = datetime(2026, 10, 7, 11, 0, tzinfo=timezone.utc)                       # 7 Oct 2026 is a Wednesday
    qs = vcip.make_questions(case, dob="14/03/1985", now=wednesday, rng=random.Random(1))
    assert len(qs) == 3 and [q["id"] for q in qs] == [1, 2, 3]
    repeat = next(q for q in qs if q["kind"] == "repeat_number")
    digits = repeat["expected"].replace(" ", "")
    assert len(digits) == 4 and digits.isdigit() and "0" not in digits and all(d in repeat["en"] for d in digits)
    assert "शून्य" not in repeat["hi"] and "संख्या" in repeat["hi"]
    seen = set()
    for seed in range(40):
        for q in vcip.make_questions(case, "14/03/1985", wednesday, random.Random(seed)):
            seen.add(q["kind"])
            if q["kind"] == "weekday":
                assert q["expected"] == "Wednesday (बुधवार)"
            if q["kind"] == "month":
                assert q["expected"] == "October (अक्टूबर)"
            if q["kind"] == "legal_name":
                assert q["expected"] == "Royal Rajasthan Spices"
            if q["kind"] == "dob":
                assert q["expected"] == "14/03/1985"
    assert seen == {"repeat_number", "weekday", "month", "legal_name", "own_name", "dob"}          # varied across calls
    assert vcip.make_questions(case, None, wednesday, random.Random(2)) != vcip.make_questions(case, None, wednesday, random.Random(3))     # not a fixed script


def test_no_date_of_birth_or_name_means_those_questions_are_not_asked():
    case = Case(id="X", slug="x", merchant_name="R", legal_name="R Ltd", entity_type="private_limited")
    for seed in range(40):
        kinds = {q["kind"] for q in vcip.make_questions(case, None, rng=random.Random(seed))}
        assert not ({"dob", "own_name"} & kinds)


# ---------------------------------------------------------------- the record and the context
def test_context_is_built_once_and_carries_the_questions_for_the_agent(at_vcip):
    ctx = at_vcip.get(f"/api/cases/{CASE}/voice-chase/context?kind=vcip").json()["data"]
    v = ctx["agent_variables"]
    assert ctx["kind"] == "vcip" and ctx["should_call"] and v["contact_name"] == "Neha Rao" and v["question_count"] == "3"
    assert all(v[f"question_{i}_hi"] for i in (1, 2, 3)) and ctx["initial_bot_message"].startswith("नमस्ते Neha Rao") and "3 आसान सवाल" in ctx["initial_bot_message"]
    assert all(isinstance(x, str) for x in v.values())
    again = at_vcip.get(f"/api/cases/{CASE}/voice-chase/context?kind=vcip").json()["data"]
    assert again["agent_variables"] == v                                                           # the same questions: created once, not per request
    detail = at_vcip.get(f"/api/cases/{CASE}").json()["data"]["vcip"]
    assert detail["status"] == "queued" and len(detail["questions"]) == 3 and "expected" in detail["questions"][0]
    assert detail["faceMatch"]["performed"] is False and "No face-matching model" in detail["faceMatch"]["note"]
    assert "V-CIP prepared" in [t["title"] for t in at_vcip.get(f"/api/cases/{CASE}").json()["data"]["timeline"]]


def test_chase_context_is_unchanged_by_the_kind_parameter(at_vcip):
    ctx = at_vcip.get(f"/api/cases/{CASE}/voice-chase/context").json()["data"]
    assert "kind" not in ctx and "question_count" not in ctx["agent_variables"]


# ---------------------------------------------------------------- the pre-interview call uses the second agent
def test_the_call_uses_the_vcip_agent_and_the_chase_agent_is_untouched(at_vcip, monkeypatch):
    for k, v in (("SARVAM_AGENT_ID", "chase-agent"), ("SARVAM_AGENT_API_KEY", "key"), ("SARVAM_CONNECTION_ID", "Twilio-x"), ("SARVAM_AGENT_PHONE_NUMBER", "+18453161334"),
                 ("SARVAM_VCIP_AGENT_ID", "vcip-agent"), ("SARVAM_VCIP_AGENT_VERSION", 2), ("SARVAM_AGENT_VERSION", 1), ("SARVAM_CALLBACK_URL", "")):
        monkeypatch.setattr(config, k, v)
    sent = []
    monkeypatch.setattr(httpx, "post", lambda url, headers, json, timeout: (sent.append(json), resp(200, {"attempt_id": "att-v"}))[1])
    out = at_vcip.post(f"/api/cases/{CASE}/voice-chase/call", json={"to_number": "+919812345678", "kind": "vcip"}).json()
    assert out["ok"] and out["data"]["attempt_id"] == "att-v"
    ac = sent[-1]["app_config"]
    assert ac["app_id"] == "vcip-agent" and ac["app_version"] == 2 and ac["agent_variables"]["question_count"] == "3" and "question_1_hi" in ac["agent_variables"]
    at_vcip.post(f"/api/cases/{CASE}/voice-chase/result", json={"outcome": "no_answer", "kind": "vcip"})           # clear the in-progress marker
    chase = at_vcip.post(f"/api/cases/{CASE}/voice-chase/call", json={"to_number": "+919812345678"}).json()
    assert chase["ok"] is False or sent[-1]["app_config"]["app_id"] == "chase-agent"                              # (no merchant issue on this seeded AUTO case)


def test_attempt_polling_and_transcript_use_the_vcip_agent(at_vcip, monkeypatch):
    monkeypatch.setattr(config, "SARVAM_AGENT_ID", "chase-agent")
    monkeypatch.setattr(config, "SARVAM_AGENT_API_KEY", "key")
    monkeypatch.setattr(config, "SARVAM_VCIP_AGENT_ID", "vcip-agent")
    urls = []

    def fake_get(url, headers, params=None, timeout=30):
        urls.append(url)
        if url.endswith("/attempts"):
            return resp(200, {"items": [{"attempt_id": "a1", "interaction_id": "20261003/x", "connectivity_status": "connected", "duration_in_seconds": 51, "end_datetime": "2026-10-03T10:00:00Z"}]})
        return resp(200, {"messages": [{"role": "assistant", "content": "नमस्ते"}, {"role": "user", "content": "जी"}]})

    monkeypatch.setattr(httpx, "get", fake_get)
    d = at_vcip.get(f"/api/cases/{CASE}/voice-chase/attempts/a1?kind=vcip").json()["data"]
    assert d["state"] == "done" and len(d["transcript"]) == 2 and all("/vcip-agent/" in u or u.endswith("/vcip-agent/attempts") for u in urls) and not any("chase-agent" in u for u in urls)


def test_result_for_a_pre_interview_goes_to_the_vcip_record_not_the_chase_history(at_vcip):
    r = at_vcip.post(f"/api/cases/{CASE}/voice-chase/result", json={
        "kind": "vcip", "outcome": "reached", "summary": "The merchant picked up (48 s).", "call_id": "20261003/abc",
        "transcript": [{"role": "agent", "text": "नमस्ते Neha Rao"}, {"role": "merchant", "text": "जी बोलिए"}]}).json()["data"]
    assert r["worth_remembering"] is False and r["voice_call_id"] is None                           # not sent to Cognee, not a chase call
    c = at_vcip.get(f"/api/cases/{CASE}").json()["data"]
    assert c["vcip"]["status"] == "interviewed" and len(c["vcip"]["transcript"]) == 2 and c["vcip"]["callId"] == "20261003/abc"
    assert not [v for v in c["voiceCalls"] if v["callId"] == "20261003/abc"]
    assert "V-CIP pre-interview completed" in [t["title"] for t in c["timeline"]]
    at_vcip.post(f"/api/cases/{CASE}/voice-chase/result", json={"kind": "vcip", "outcome": "no_answer", "summary": "No answer."})
    assert at_vcip.get(f"/api/cases/{CASE}").json()["data"]["vcip"]["status"] == "interviewed"          # a later failed retry does not undo it


def test_a_finished_pre_interview_call_releases_the_one_call_at_a_time_guard(at_vcip, monkeypatch):
    for k, v in (("SARVAM_AGENT_ID", "chase-agent"), ("SARVAM_AGENT_API_KEY", "key"), ("SARVAM_CONNECTION_ID", "Twilio-x"), ("SARVAM_AGENT_PHONE_NUMBER", "+18453161334"),
                 ("SARVAM_VCIP_AGENT_ID", "vcip-agent"), ("SARVAM_CALLBACK_URL", "")):
        monkeypatch.setattr(config, k, v)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: resp(200, {"attempt_id": "att-g"}))
    at_vcip.post(f"/api/cases/{CASE}/voice-chase/call", json={"to_number": "+919812345678", "kind": "vcip"})
    blocked = at_vcip.post(f"/api/cases/{CASE}/action", json={"action": "vcip_call", "actor": "compliance", "phone": "+919812345678"})
    assert blocked.status_code == 409 and "still in progress" in blocked.json()["detail"]
    at_vcip.post(f"/api/cases/{CASE}/voice-chase/result", json={"kind": "vcip", "outcome": "no_answer", "summary": "No answer."})
    free = at_vcip.post(f"/api/cases/{CASE}/action", json={"action": "vcip_call", "actor": "compliance", "phone": "+919812345678"})
    assert free.status_code == 200


def test_an_unanswered_pre_interview_stays_queued(at_vcip):
    at_vcip.post(f"/api/cases/{CASE}/voice-chase/result", json={"kind": "vcip", "outcome": "busy", "summary": "The line was busy."})
    d = at_vcip.get(f"/api/cases/{CASE}").json()["data"]
    assert d["vcip"]["status"] == "queued" and "V-CIP pre-interview not completed" in [t["title"] for t in d["timeline"]]


# ---------------------------------------------------------------- the human actions
def test_vcip_call_is_a_compliance_action_and_needs_the_second_agent(at_vcip, monkeypatch):
    monkeypatch.setattr(config, "SARVAM_VCIP_AGENT_ID", "")
    r = at_vcip.post(f"/api/cases/{CASE}/action", json={"action": "vcip_call", "actor": "compliance", "phone": "+919812345678"})
    assert r.status_code == 422 and "SARVAM_VCIP_AGENT_ID" in r.json()["detail"] and "SARVAM_VCIP_AGENT_SETUP.md" in r.json()["detail"]
    monkeypatch.setattr(config, "SARVAM_VCIP_AGENT_ID", "vcip-agent")
    sent = {}
    monkeypatch.setattr(config, "N8N_VOICE_WEBHOOK_URL", "http://n8n.test/webhook/karyakarta-voice-chase")
    monkeypatch.setattr(httpx, "post", lambda url, json, timeout: (sent.update(json=json), httpx.Response(200, request=httpx.Request("POST", url)))[1])
    for actor in ("agent", "merchant", "kam"):
        assert at_vcip.post(f"/api/cases/{CASE}/action", json={"action": "vcip_call", "actor": actor, "phone": "+919812345678"}).status_code == 403
    ok = at_vcip.post(f"/api/cases/{CASE}/action", json={"action": "vcip_call", "actor": "compliance", "phone": "+919812345678"})
    assert ok.status_code == 200 and sent["json"] == {"case_id": CASE, "to_number": "+919812345678", "kind": "vcip"}
    assert "V-CIP pre-interview requested" in [t["title"] for t in ok.json()["data"]["timeline"]]


def test_signoff_is_compliance_only_needs_stage_7_and_records_whether_an_interview_happened(at_vcip):
    for actor in ("agent", "merchant", "kam"):
        assert at_vcip.post(f"/api/cases/{CASE}/action", json={"action": "vcip_signoff", "actor": actor}).status_code == 403, actor
    at_vcip.post(f"/api/cases/{CASE}/voice-chase/result", json={"kind": "vcip", "outcome": "reached", "summary": "ok",
                                                                   "transcript": [{"role": "agent", "text": "a"}, {"role": "merchant", "text": "b"}]})
    r = at_vcip.post(f"/api/cases/{CASE}/action", json={"action": "vcip_signoff", "actor": "compliance"})
    assert r.status_code == 200 and r.json()["data"]["stage"] == 8 and r.json()["data"]["stages"][7]["label"] == "Bank Settlement Test"
    d = r.json()["data"]
    assert d["vcip"]["status"] == "signed_off" and d["vcip"]["signedOffBy"] == "compliance"
    assert d["timeline"][-1]["title"] == "V-CIP signed off" and "WITHOUT" not in d["timeline"][-1]["detail"]
    assert at_vcip.post(f"/api/cases/{CASE}/action", json={"action": "vcip_signoff", "actor": "compliance"}).status_code == 409        # stage moved on


def test_signing_off_without_an_interview_is_allowed_but_flagged_on_the_timeline(at_vcip):
    r = at_vcip.post(f"/api/cases/{CASE}/action", json={"action": "vcip_signoff", "actor": "compliance"})
    assert r.status_code == 200
    last = r.json()["data"]["timeline"][-1]
    assert last["title"] == "V-CIP signed off" and "WITHOUT a completed Hindi pre-interview" in last["detail"] and last["tone"] == "warning"
