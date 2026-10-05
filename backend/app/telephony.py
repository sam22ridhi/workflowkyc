"""Outbound voice calls through Sarvam "Instant Outbound" (agent + a connected Twilio number).

place_call()      POST apps.sarvam.ai/api/outbounds/v1/orgs/{org}/workspaces/{ws}/outbounds   -> attempt_id
attempt_status()  GET  apps.sarvam.ai/api/analytics/v1/{org}/{ws}/{app}/attempts              (filter by attempt_id)
transcript()      GET  apps.sarvam.ai/api/analytics/v1/{org}/{ws}/{app}/transcripts/{interaction_id}

The result is POLLED (n8n calls attempt_status until the call ends), so no public webhook URL is needed. If
SARVAM_CALLBACK_URL is set, Sarvam is also given it as the call-completed webhook.
Auth for all three is the header X-API-Key (the agent API key).
"""
import json
import re
from datetime import datetime, timedelta, timezone

import httpx

from app import config

OUTBOUND_URL = "https://apps.sarvam.ai/api/outbounds/v1/orgs/{org}/workspaces/{ws}/outbounds"
ANALYTICS_URL = "https://apps.sarvam.ai/api/analytics/v1/{org}/{ws}/{app}"
E164 = re.compile(r"^\+[1-9]\d{7,14}$")


class TelephonyError(Exception):
    """A readable reason a call could not be placed or checked. Never contains the API key."""


def normalise_number(raw: str, default_country_code: str = "+91") -> str:
    """'98123 45678' -> '+919812345678' (10-digit numbers are taken as Indian); '+1 845 ...' keeps its code."""
    s = re.sub(r"[\s\-().]", "", (raw or "").strip())
    if s.startswith("00"):
        s = "+" + s[2:]
    if re.fullmatch(r"\d{10}", s):
        s = default_country_code + s
    elif re.fullmatch(r"0\d{10}", s):
        s = default_country_code + s[1:]
    elif re.fullmatch(r"\d{11,15}", s):
        s = "+" + s
    if not E164.match(s):
        raise TelephonyError(f"“{raw}” is not a valid phone number. Use the international format, for example +919812345678.")
    return s


def mask(number: str) -> str:
    return number[:3] + "•" * max(len(number) - 6, 2) + number[-3:]


def configured(app_id: str | None = None, app_name: str = "SARVAM_AGENT_ID") -> str | None:
    """None when everything needed to place a call is set, else the name of what is missing."""
    for name, value in ((app_name, app_id or config.SARVAM_AGENT_ID), ("SARVAM_API_KEY_NEW_FOR_VOICE", config.SARVAM_AGENT_API_KEY),
                        ("SARVAM_CONNECTION_ID", config.SARVAM_CONNECTION_ID), ("SARVAM_AGENT_PHONE_NUMBER", config.SARVAM_AGENT_PHONE_NUMBER)):
        if not value:
            return name
    return None


def _headers() -> dict:
    return {"X-API-Key": config.SARVAM_AGENT_API_KEY, "Content-Type": "application/json"}


def _explain(r: httpx.Response) -> str:
    """Turn a Sarvam error response into one sentence for the case timeline."""
    try:
        body = r.json()
        detail = ((body.get("error") or {}).get("data") or {}).get("details") or (body.get("error") or {}).get("message") or body.get("detail")
    except ValueError:
        detail = r.text[:200]
    detail = str(detail)[:300]
    hint = {
        401: " Check SARVAM_API_KEY_NEW_FOR_VOICE (it must be an agent API key).",
        403: " The key may not be allowed to place calls for this agent or connection.",
        404: " Check SARVAM_AGENT_ID, SARVAM_AGENT_VERSION and SARVAM_CONNECTION_ID.",
    }.get(r.status_code, "")
    return f"Sarvam refused the call (HTTP {r.status_code}): {detail}.{hint}"


def place_call(to_number: str, agent_variables: dict, opening_line: str, language: str, case_id: str,
               app_id: str | None = None, app_version: int | None = None, app_name: str = "SARVAM_AGENT_ID") -> dict:
    """Start the outbound call with the chase agent (default) or another agent (the V-CIP pre-interview agent).
    Returns {attempt_id, completion: 'poll' | 'webhook'}."""
    missing = configured(app_id, app_name)
    if missing:
        raise TelephonyError(f"Phone calling is not configured: {missing} is empty in backend/.env.")
    body = {
        "app_config": {
            "app_id": app_id or config.SARVAM_AGENT_ID,
            "app_version": app_version or config.SARVAM_AGENT_VERSION,
            "connection_config": {"connection_id": config.SARVAM_CONNECTION_ID, "agent_phone_number": config.SARVAM_AGENT_PHONE_NUMBER},
            "agent_variables": {k: str(v) for k, v in agent_variables.items()},
            "app_overrides": {"initial_bot_message": opening_line, "initial_language_name": language},
        },
        "user_config": {"user_phone_number": to_number},
    }
    if config.SARVAM_CALLBACK_URL:
        body["webhook_config"] = {"url": config.SARVAM_CALLBACK_URL, "metadata": {"case_id": case_id}}
    url = OUTBOUND_URL.format(org=config.SARVAM_ORG_ID, ws=config.SARVAM_WORKSPACE_ID)
    try:
        r = httpx.post(url, headers=_headers(), json=body, timeout=30)
    except httpx.HTTPError as e:
        raise TelephonyError(f"Could not reach Sarvam to place the call: {type(e).__name__}.") from e
    if r.status_code >= 300:
        raise TelephonyError(_explain(r))
    attempt = r.json().get("attempt_id")
    if not attempt:
        raise TelephonyError("Sarvam accepted the request but returned no attempt id.")
    return {"attempt_id": attempt, "completion": "webhook" if config.SARVAM_CALLBACK_URL else "poll"}


# ---------------------------------------------------------------- reading the result
NO_FAILURE = {"", "no_failure_reason", "none", "null"}      # Sarvam sends the literal "NO_FAILURE_REASON" for a call that worked


def _failure(item: dict) -> str | None:
    reason = str(item.get("failure_reason") or "").strip()
    return None if reason.lower() in NO_FAILURE else reason


FINISHED_STATUSES = {"failed", "no_answer", "no-answer", "busy", "unanswered", "cancelled", "canceled", "completed", "ended"}
TWILIO_HINTS = {
    21219: "Your Twilio account is a trial account, which can call only verified numbers. In the Twilio console add this number under "
           "Verified Caller IDs (Phone Numbers > Manage > Verified Caller IDs), or upgrade the Twilio account.",
    21215: "Twilio is not allowed to call this country yet. Enable it under Voice > Settings > Geo Permissions in the Twilio console.",
    21216: "Twilio is not allowed to call this country yet. Enable it under Voice > Settings > Geo Permissions in the Twilio console.",
    21408: "Twilio is not allowed to call this country yet. Enable it under Voice > Settings > Geo Permissions in the Twilio console.",
}


def _real(value):
    """Sarvam fills missing ids with placeholders like 'NO_INTERACTION_ID'."""
    text = str(value or "")
    return None if not text or text.startswith("NO_") else text


AGENT_NEVER_JOINED = (
    "The call was placed, but Sarvam's agent never joined it: no conversation was created. If your phone rang and you heard an English "
    "recorded message, that is Twilio's trial-account announcement. It waits for a keypress before connecting, and hangs up if none "
    "comes. Press any key when you hear it, or upgrade the Twilio account to remove the announcement."
)


def _finished(item: dict) -> bool:
    """A call that failed before it started has no end time, so the status must count too."""
    return bool(item.get("end_datetime")) or str(item.get("connectivity_status") or "").strip().lower() in FINISHED_STATUSES


def explain_failure(reason: str | None) -> str | None:
    """'twilio: {"code":21219,"message":"..."}' -> a sentence with what to do about it."""
    if not reason:
        return None
    m = re.search(r"twilio:\s*(\{.*\})", reason, re.S)
    if not m:
        return reason
    try:
        body = json.loads(m.group(1))
    except ValueError:
        return reason
    code, message = body.get("code"), str(body.get("message") or "").strip()
    hint = TWILIO_HINTS.get(code)
    return f"Twilio refused the call (error {code}): {message}" + (f" {hint}" if hint else "")


def _outcome(item: dict) -> str:
    text = " ".join([str(item.get("connectivity_status") or ""), str(item.get("status") or ""), _failure(item) or ""]).lower()
    if "no_answer" in text or "no answer" in text or "unanswered" in text or "not answered" in text:
        return "no_answer"
    if "busy" in text:
        return "busy"
    if _failure(item) or "fail" in text or "error" in text:
        return "failed"
    return "reached"


def attempt_status(attempt_id: str, app_id: str | None = None) -> dict:
    """{state: 'pending'|'done', outcome, duration, interaction_id, failure_reason}. 'pending' until Sarvam reports an end time."""
    now = datetime.now(timezone.utc)
    params = {
        "start_datetime": (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_datetime": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 5,
        "filter_conditions": '[{"id":"a","field":"attempt_id","operator":"equals","value":"%s"}]' % attempt_id.replace('"', ""),
    }
    url = ANALYTICS_URL.format(org=config.SARVAM_ORG_ID, ws=config.SARVAM_WORKSPACE_ID, app=app_id or config.SARVAM_AGENT_ID) + "/attempts"
    try:
        r = httpx.get(url, headers=_headers(), params=params, timeout=30)
    except httpx.HTTPError as e:
        raise TelephonyError(f"Could not reach Sarvam to check the call: {type(e).__name__}.") from e
    if r.status_code >= 300:
        raise TelephonyError(_explain(r))
    items = [i for i in (r.json().get("items") or []) if i.get("attempt_id") == attempt_id] or []
    if not items:
        return {"state": "pending", "outcome": None, "note": "Sarvam has no record of this attempt yet."}
    item = items[0]
    if not _finished(item):
        return {"state": "pending", "outcome": None, "note": "The call is still in progress."}
    outcome, reason = _outcome(item), explain_failure(_failure(item))
    if outcome == "failed" and not reason and not _real(item.get("interaction_id")):
        reason = AGENT_NEVER_JOINED                      # failed, no reason given, no conversation: the agent never got on the line
    return {"state": "done", "outcome": outcome, "duration": item.get("duration_in_seconds"),
            "interaction_id": _real(item.get("interaction_id")),
            "failure_reason": reason,
            "messages": item.get("num_messages")}


def _turns(node) -> list[dict]:
    """Find the list of conversation turns in a transcript response whose exact shape is not documented."""
    if isinstance(node, list):
        if node and all(isinstance(x, dict) for x in node) and any(("role" in x or "speaker" in x) for x in node):
            return node
        for x in node:
            found = _turns(x)
            if found:
                return found
    elif isinstance(node, dict):
        for key in ("interaction_transcript", "transcript", "turns", "messages", "items", "data", "conversation"):
            if key in node:
                found = _turns(node[key])
                if found:
                    return found
        for v in node.values():
            found = _turns(v)
            if found:
                return found
    return []


def transcript(interaction_id: str, app_id: str | None = None) -> list[dict]:
    """[{role: 'agent'|'merchant', text}]. Empty if Sarvam has no transcript (call did not connect) or it cannot be read."""
    url = ANALYTICS_URL.format(org=config.SARVAM_ORG_ID, ws=config.SARVAM_WORKSPACE_ID, app=app_id or config.SARVAM_AGENT_ID) + f"/transcripts/{interaction_id}"
    try:
        r = httpx.get(url, headers=_headers(), timeout=30)
    except httpx.HTTPError:
        return []
    if r.status_code >= 300:
        return []
    out = []
    for t in _turns(r.json()):
        role = str(t.get("role") or t.get("speaker") or "").lower()
        text = t.get("en_text") or t.get("text") or t.get("content") or t.get("message") or t.get("transcript") or ""
        if str(text).strip():
            out.append({"role": "agent" if role in {"agent", "assistant", "bot", "ai"} else "merchant", "text": str(text).strip()})
    return out
