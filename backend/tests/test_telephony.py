"""Outbound voice calls. Sarvam is mocked: no real call is ever placed by the tests."""
import httpx
import pytest

from app import config, telephony


@pytest.fixture
def phone_config(monkeypatch):
    monkeypatch.setattr(config, "SARVAM_AGENT_ID", "agent-x")
    monkeypatch.setattr(config, "SARVAM_AGENT_API_KEY", "voice-key-secret")
    monkeypatch.setattr(config, "SARVAM_CONNECTION_ID", "Twilio-test-conn")
    monkeypatch.setattr(config, "SARVAM_AGENT_PHONE_NUMBER", "+18453161334")
    monkeypatch.setattr(config, "SARVAM_AGENT_VERSION", 3)
    monkeypatch.setattr(config, "SARVAM_CALLBACK_URL", "")


def resp(status, body, url="https://x.test"):
    return httpx.Response(status, json=body, request=httpx.Request("POST", url))


def test_number_normalisation():
    n = telephony.normalise_number
    assert n("98123 45678") == "+919812345678" and n("09812345678") == "+919812345678"
    assert n("+1 (845) 316-1334") == "+18453161334" and n("00919812345678") == "+919812345678" and n("919812345678") == "+919812345678"
    for bad in ("", "abc", "12345", "+0123456789", "98123"):
        with pytest.raises(telephony.TelephonyError):
            n(bad)
    assert telephony.mask("+919812345678") == "+91•••••••678"


def test_place_call_builds_the_sarvam_request(phone_config, monkeypatch):
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, headers=headers, json=json)
        return resp(200, {"attempt_id": "att-1"})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = telephony.place_call("+919812345678", {"issue_count": 2, "merchant_name": "Royal"}, "नमस्ते", "Hindi", "KYB-20817")
    assert out == {"attempt_id": "att-1", "completion": "poll"}
    assert sent["url"].endswith("/orgs/019f298f-eba1-725a-a645-5db63306d773/workspaces/019f298f-eba7-7b7a-8f83-a767c766c059/outbounds")
    assert sent["headers"]["X-API-Key"] == "voice-key-secret"
    ac = sent["json"]["app_config"]
    assert ac["app_id"] == "agent-x" and ac["app_version"] == 3
    assert ac["connection_config"] == {"connection_id": "Twilio-test-conn", "agent_phone_number": "+18453161334"}
    assert ac["agent_variables"] == {"issue_count": "2", "merchant_name": "Royal"}            # all strings
    assert ac["app_overrides"] == {"initial_bot_message": "नमस्ते", "initial_language_name": "Hindi"}
    assert sent["json"]["user_config"] == {"user_phone_number": "+919812345678"} and "webhook_config" not in sent["json"]


def test_callback_url_is_added_only_when_configured(phone_config, monkeypatch):
    monkeypatch.setattr(config, "SARVAM_CALLBACK_URL", "https://tunnel.example/webhook/karyakarta-voice-result")
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(json=json)
        return resp(200, {"attempt_id": "a"})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert telephony.place_call("+919812345678", {}, "x", "Hindi", "KYB-1")["completion"] == "webhook"
    assert sent["json"]["webhook_config"] == {"url": "https://tunnel.example/webhook/karyakarta-voice-result", "metadata": {"case_id": "KYB-1"}}


def test_errors_are_readable_and_never_leak_the_key(phone_config, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: resp(404, {"error": {"data": {"details": "App not found"}}}))
    with pytest.raises(telephony.TelephonyError) as e:
        telephony.place_call("+919812345678", {}, "x", "Hindi", "KYB-1")
    assert "HTTP 404" in str(e.value) and "App not found" in str(e.value) and "SARVAM_CONNECTION_ID" in str(e.value)
    assert "voice-key-secret" not in str(e.value)
    monkeypatch.setattr(config, "SARVAM_CONNECTION_ID", "")
    with pytest.raises(telephony.TelephonyError, match="SARVAM_CONNECTION_ID is empty"):
        telephony.place_call("+919812345678", {}, "x", "Hindi", "KYB-1")


def test_attempt_status_pending_then_done(phone_config, monkeypatch):
    calls = []

    def fake_get(url, headers, params, timeout):
        calls.append(params)
        item = {"attempt_id": "att-1", "interaction_id": "int-9", "connectivity_status": "connected", "duration_in_seconds": 41.2,
                "num_messages": 6, "failure_reason": None, "end_datetime": None}
        if len(calls) == 1:
            return resp(200, {"items": []})
        if len(calls) == 2:
            return resp(200, {"items": [item]})
        return resp(200, {"items": [{**item, "end_datetime": "2026-10-03T10:00:00Z"}, {"attempt_id": "other"}]})

    monkeypatch.setattr(httpx, "get", fake_get)
    assert telephony.attempt_status("att-1")["state"] == "pending"                       # not known yet
    assert telephony.attempt_status("att-1")["state"] == "pending"                       # in progress (no end time)
    done = telephony.attempt_status("att-1")
    assert done["state"] == "done" and done["outcome"] == "reached" and done["duration"] == 41.2 and done["interaction_id"] == "int-9"
    assert '"field":"attempt_id"' in calls[0]["filter_conditions"] and "att-1" in calls[0]["filter_conditions"]


@pytest.mark.parametrize("item,outcome", [
    ({"connectivity_status": "no_answer"}, "no_answer"),
    ({"connectivity_status": "busy"}, "busy"),
    ({"connectivity_status": "failed", "failure_reason": "provider error"}, "failed"),
    ({"connectivity_status": "connected"}, "reached"),
    ({"connectivity_status": "connected", "failure_reason": "NO_FAILURE_REASON"}, "reached"),      # the real value for a call that worked
    ({"connectivity_status": "unknown", "failure_reason": "Number not allowed on trial account"}, "failed"),
])
def test_outcome_mapping(item, outcome):
    assert telephony._outcome(item) == outcome


def test_a_call_twilio_refused_is_finished_at_once_with_a_plain_reason(phone_config, monkeypatch):
    # the real record Sarvam holds for a trial-account refusal: no end time, status failed, placeholders for the ids
    real = {"attempt_id": "att-1", "interaction_id": "NO_INTERACTION_ID", "connectivity_status": "failed", "end_datetime": None,
            "start_datetime": None, "duration_in_seconds": 0.0, "num_messages": 0, "channel_direction": "outbound",
            "failure_reason": 'twilio: {"code":21219,"message":"The number +918828000465 is unverified. Trial accounts may only make calls to verified numbers.",'
                              '"more_info":"https://www.twilio.com/docs/errors/21219","status":400}'}
    monkeypatch.setattr(httpx, "get", lambda *a, **k: resp(200, {"items": [real]}))
    done = telephony.attempt_status("att-1")
    assert done["state"] == "done" and done["outcome"] == "failed" and done["interaction_id"] is None
    assert "Twilio refused the call (error 21219)" in done["failure_reason"] and "Verified Caller IDs" in done["failure_reason"]
    assert "+918828000465 is unverified" in done["failure_reason"]


def test_failed_with_no_reason_and_no_conversation_explains_the_trial_announcement(phone_config, monkeypatch):
    # the real record of a call that rang and was answered but never reached the agent (attempt f25960e0)
    real = {"attempt_id": "att-2", "interaction_id": "NO_INTERACTION_ID", "connectivity_status": "failed", "failure_reason": "NO_FAILURE_REASON",
            "end_datetime": None, "duration_in_seconds": 0.0, "num_messages": 0, "channel_direction": "outbound"}
    monkeypatch.setattr(httpx, "get", lambda *a, **k: resp(200, {"items": [real]}))
    done = telephony.attempt_status("att-2")
    assert done["state"] == "done" and done["outcome"] == "failed" and done["interaction_id"] is None
    assert "agent never joined" in done["failure_reason"] and "trial-account announcement" in done["failure_reason"] and "Press any key" in done["failure_reason"]


def test_failure_explanations():
    assert telephony.explain_failure(None) is None and telephony.explain_failure("provider down") == "provider down"
    geo = telephony.explain_failure('twilio: {"code":21215,"message":"Account not authorized to call +91"}')
    assert "Geo Permissions" in geo
    assert telephony.explain_failure('twilio: {"code":99999,"message":"odd"}') == "Twilio refused the call (error 99999): odd"


def test_transcript_parsing_tolerates_shapes(phone_config, monkeypatch):
    bodies = (
        {"interaction_transcript": [{"role": "agent", "en_text": "Hello"}, {"role": "user", "en_text": "Yes tell me"}]},
        {"interaction_id": "20261002/x", "messages": [{"turn_id": 1, "role": "assistant", "content": "Hello", "language_name": "Hindi"},
                                                      {"turn_id": 2, "role": "user", "content": "Yes tell me", "language_name": "UNKNOWN"}]},   # real shape
        {"data": {"turns": [{"role": "assistant", "text": "Hello"}, {"role": "user", "text": "Yes tell me"}, {"role": "user", "text": " "}]}},
        [{"speaker": "agent", "content": "Hello"}, {"speaker": "user", "content": "Yes tell me"}],
    )
    for body in bodies:
        monkeypatch.setattr(httpx, "get", lambda *a, _b=body, **k: resp(200, _b))
        assert telephony.transcript("int-1") == [{"role": "agent", "text": "Hello"}, {"role": "merchant", "text": "Yes tell me"}]
    monkeypatch.setattr(httpx, "get", lambda *a, **k: resp(404, {}))
    assert telephony.transcript("int-1") == []


# ---------------------------------------------------------------- routes
def test_voice_action_validates_the_number_before_changing_anything(client, monkeypatch):
    monkeypatch.setattr(config, "N8N_VOICE_WEBHOOK_URL", "")
    before = client.get("/api/cases/KYB-20817").json()["data"]["status"]
    r = client.post("/api/cases/KYB-20817/action", json={"action": "voice", "channel": "voice", "phone": "12345"})
    assert r.status_code == 422 and "not a valid phone number" in r.json()["detail"]
    assert client.get("/api/cases/KYB-20817").json()["data"]["status"] == before          # nothing changed


def test_voice_action_passes_the_number_to_n8n_and_remembers_it(client, monkeypatch):
    sent = {}

    def fake_post(url, json, timeout):
        sent.update(url=url, json=json)
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(config, "N8N_VOICE_WEBHOOK_URL", "http://n8n.test/webhook/karyakarta-voice-chase")
    monkeypatch.setattr(httpx, "post", fake_post)
    r = client.post("/api/cases/KYB-20816/action", json={"action": "voice", "channel": "voice", "phone": "98123 45678"})
    assert r.status_code == 200 and sent["json"] == {"case_id": "KYB-20816", "to_number": "+919812345678"}
    timeline = r.json()["data"]["timeline"]
    assert any("+91•••••••678" in t["detail"] for t in timeline) and "9812345678" not in str(timeline)   # masked on the timeline
    # no phone given the second time: the remembered number is used once the first call has finished
    client.post("/api/cases/KYB-20816/voice-chase/result", json={"outcome": "no_answer"})
    sent.clear()
    assert client.post("/api/cases/KYB-20816/action", json={"action": "voice", "channel": "voice"}).status_code == 200
    assert sent["json"]["to_number"] == "+919812345678"
    # whatsapp / email never place a call and need no number
    sent.clear()
    assert client.post("/api/cases/KYB-20816/action", json={"action": "voice", "channel": "whatsapp"}).status_code == 200 and sent == {}


def test_a_second_call_is_blocked_while_one_is_in_progress(client, phone_config, monkeypatch):
    monkeypatch.setattr(config, "N8N_VOICE_WEBHOOK_URL", "")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: resp(200, {"attempt_id": "att-9"}))
    placed = client.post("/api/cases/KYB-20817/voice-chase/call", json={"to_number": "+919812345678"})
    assert placed.json()["data"]["attempt_id"] == "att-9"
    r = client.post("/api/cases/KYB-20817/action", json={"action": "voice", "channel": "voice", "phone": "+919812345678"})
    assert r.status_code == 409 and "still in progress" in r.json()["detail"]
    client.post("/api/cases/KYB-20817/voice-chase/result", json={"outcome": "reached", "summary": "done"})          # the call finished
    again = client.post("/api/cases/KYB-20817/action", json={"action": "voice", "channel": "voice", "phone": "+919812345678"})
    assert again.status_code == 200


def test_call_route_reports_failures_as_ok_false_and_nothing_to_call_about(client, phone_config, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: resp(422, {"error": {"data": {"details": "Invalid phone number"}}}))
    r = client.post("/api/cases/KYB-20817/voice-chase/call", json={"to_number": "+919812345678"})
    assert r.status_code == 200 and r.json()["ok"] is False and "Invalid phone number" in r.json()["error"]
    r = client.post("/api/cases/KYB-20818/voice-chase/call", json={"to_number": "+919812345678"})                   # seeded AUTO case
    assert r.json()["ok"] is False and "nothing to call about" in r.json()["error"]


def test_attempt_route_returns_outcome_summary_and_transcript(client, phone_config, monkeypatch):
    def fake_get(url, headers, params=None, timeout=30):
        if url.endswith("/attempts"):
            return resp(200, {"items": [{"attempt_id": "att-1", "interaction_id": "int-9", "connectivity_status": "connected",
                                         "duration_in_seconds": 42.0, "end_datetime": "2026-10-03T10:00:00Z"}]})
        return resp(200, {"interaction_transcript": [{"role": "agent", "en_text": "Hello"}, {"role": "user", "en_text": "Yes"}]})

    monkeypatch.setattr(httpx, "get", fake_get)
    d = client.get("/api/cases/KYB-20817/voice-chase/attempts/att-1").json()["data"]
    assert d["state"] == "done" and d["outcome"] == "reached" and d["call_id"] == "int-9" and d["summary"] == "The merchant picked up (42 s)."
    assert d["transcript"] == [{"role": "agent", "text": "Hello"}, {"role": "merchant", "text": "Yes"}]
    monkeypatch.setattr(httpx, "get", lambda *a, **k: resp(401, {"error": {"message": "Unauthorized"}}))
    assert client.get("/api/cases/KYB-20817/voice-chase/attempts/att-1").status_code == 502
