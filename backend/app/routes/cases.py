import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from typing import Literal

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app import config, pipeline
from app import crm_form as crm_builder
from app.checks import cross_check
from app.registry import mock_registry
from app import voice_agent
from app.db import audit, engine, get_session
from app.doctypes import DOC_TYPES, guess_doc_type
from app.models import AuditEvent, Case, CrmOverride, Document, VoiceCall, utcnow
from app.schemas_api import (
    ActionRequest, CaseDetail, CaseList, Envelope, Kpis, RejectedFile, UploadAccepted,
)
from app.serializers import case_detail, case_row, doc_out

router = APIRouter(prefix="/api")


def get_case(session: Session, case_id: str) -> Case:
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    return case


# ---------- list / detail ----------
@router.get("/cases", response_model=Envelope[CaseList])
def list_cases(session: Session = Depends(get_session)):
    cases = list(session.exec(select(Case).order_by(Case.created_at)))
    rows = [case_row(session, c) for c in cases]
    week_ago = utcnow() - timedelta(days=7)
    kpis = Kpis(
        totalOpen=sum(1 for c in cases if c.status != "live"),
        newThisWeek=sum(1 for c in cases if (c.created_at if c.created_at.tzinfo else c.created_at.replace(tzinfo=timezone.utc)) > week_ago),
        pendingAiVerification=sum(1 for c in cases if c.status == "ai_verifying"),
        awaitingMerchant=sum(1 for c in cases if c.status in {"awaiting_merchant", "docs_pending"}),
        readyForSubmission=sum(1 for c in cases if c.status == "ready_for_review"),
        escalations=sum(1 for r in rows if r.route == "ESCALATE"),
    )
    return Envelope(data=CaseList(kpis=kpis, items=rows))


@router.get("/cases/{case_id}", response_model=Envelope[CaseDetail])
def read_case(case_id: str, session: Session = Depends(get_session)):
    return Envelope(data=case_detail(session, get_case(session, case_id)))


@router.get("/cases/{case_id}/timeline")
def case_timeline(case_id: str, session: Session = Depends(get_session)):
    detail = case_detail(session, get_case(session, case_id))
    return {"ok": True, "data": {"case_id": case_id, "items": [t.model_dump() for t in detail.timeline]}}


# ---------- documents: batch upload ----------
def _save_one(case_id: str, upload: UploadFile) -> tuple[str, Path, int, str] | str:
    """Stream to disk while hashing. Returns (doc_id, path, size, sha256) or a rejection reason."""
    name = Path(upload.filename or "upload").name
    ext = Path(name).suffix.lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        return f"Unsupported type '{ext or 'none'}'. Allowed: pdf, jpg, png."
    doc_id = uuid.uuid4().hex[:12]
    folder = config.STORAGE_DIR / case_id
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{doc_id}_{name}"
    sha, size = hashlib.sha256(), 0
    try:
        with open(dest, "wb") as out:
            while chunk := upload.file.read(1024 * 1024):
                size += len(chunk)
                if size > config.MAX_UPLOAD_BYTES:
                    raise ValueError("File exceeds the 25 MB limit.")
                sha.update(chunk)
                out.write(chunk)
        if size == 0:
            raise ValueError("File is empty.")
    except ValueError as e:
        dest.unlink(missing_ok=True)
        return str(e)
    return doc_id, dest, size, sha.hexdigest()


@router.post("/cases/{case_id}/documents", response_model=Envelope[UploadAccepted], status_code=202)
def upload_documents(
    case_id: str,
    background: BackgroundTasks,
    files: list[UploadFile] = File(default=[]),
    file: UploadFile | None = File(default=None),          # legacy single-file field
    slot: str | None = Form(default=None),                 # merchant UI slot, e.g. tax_gst
    kind: str | None = Form(default=None),                 # legacy: treated as slot/type hint
    doc_types: list[str] = Form(default=[]),               # optional per-file type hints, same order as files
    session: Session = Depends(get_session),
):
    case = get_case(session, case_id)
    uploads = list(files) + ([file] if file else [])
    if not uploads:
        raise HTTPException(400, "No files received. Send one or more 'files' parts.")

    accepted: list[Document] = []
    rejected: list[RejectedFile] = []
    for i, up in enumerate(uploads):
        result = _save_one(case_id, up)
        if isinstance(result, str):
            rejected.append(RejectedFile(filename=up.filename or "upload", reason=result))
            continue
        doc_id, path, size, digest = result
        hint = doc_types[i] if i < len(doc_types) else (kind if kind in DOC_TYPES else None)
        doc = Document(
            id=doc_id, case_id=case_id, slot=slot or kind, doc_type=guess_doc_type(up.filename or "", slot or kind, hint),
            filename=Path(up.filename or "upload").name, path=str(path),
            mime=config.ALLOWED_EXTENSIONS[path.suffix.lower()], size_bytes=size, sha256=digest,
        )
        session.add(doc)
        accepted.append(doc)
    session.commit()

    for d in accepted:
        audit(session, case_id, "merchant", "Document uploaded",
              f"{d.filename} ({DOC_TYPES.get(d.doc_type, d.doc_type)}) · SHA-256 {d.sha256[:12]}…", "neutral", d.id)
    for r in rejected:
        audit(session, case_id, "agent", "Upload rejected", f"{r.filename}: {r.reason}", "warning")

    pipeline_used = "none"
    if accepted:
        case.status = "ai_verifying"
        case.stage = max(case.stage, 3)
        session.add(case)
        session.commit()
        ids = [d.id for d in accepted]
        # Respond immediately (202); trigger n8n / fallback off the request path.
        background.add_task(pipeline.trigger, case_id, ids)
        pipeline_used = "queued"

    session.expire_all()
    return JSONResponse(
        status_code=202,
        content=Envelope(data=UploadAccepted(
            case_id=case_id, doc_ids=[d.id for d in accepted], rejected=rejected, pipeline=pipeline_used,
            documents=[doc_out(session.get(Document, d.id)) for d in accepted],
        )).model_dump(mode="json"),
    )


@router.get("/cases/{case_id}/documents")
def list_documents(case_id: str, session: Session = Depends(get_session)):
    get_case(session, case_id)
    docs = session.exec(select(Document).where(Document.case_id == case_id).order_by(Document.created_at))
    return {"ok": True, "data": [doc_out(d).model_dump(mode="json") for d in docs]}


# ---------- actions ----------
ACTIONS = {
    # action: (actor default, event title, detail, case.status, stage, tone)
    "voice": ("kam", "Voice chase requested", "KAM asked the voice agent to contact the merchant about the open items.", "awaiting_merchant", None, "ai"),
    "request": ("kam", "Information requested", "KAM requested corrections from the merchant.", "awaiting_merchant", None, "neutral"),
    "approve": ("kam", "KAM approved & submitted to Compliance", "KAM review complete; case forwarded to the checker.", "ready_for_review", 5, "success"),
    "submit_to_compliance": ("kam", "Submitted to Compliance (Checker)", "KAM review complete; case forwarded to the checker.", "ready_for_review", 5, "success"),
    "send_back": ("compliance", "Sent back to KAM", "Checker returned the case for rework.", "needs_attention", 4, "warning"),
    "compliance_approve": ("compliance", "Compliance approved", "Four-eyes check passed; moving to bank settlement test.", "ready_for_review", 6, "success"),
}


# Who may do what. Decisions are human-only: the agent (and the merchant) can never approve, submit or send back.
# Chasing the merchant is not a decision, so the agent may do it. Person-level four-eyes (maker != checker) needs real
# user identities; the demo has roles only, so it enforces role and stage.
ACTION_ROLES = {
    "voice": {"kam", "agent"}, "request": {"kam", "agent"},
    "approve": {"kam"}, "submit_to_compliance": {"kam"},
    "send_back": {"compliance"}, "compliance_approve": {"compliance"},
}


def _authorise_action(case: Case, body: ActionRequest) -> None:
    allowed = ACTION_ROLES[body.action]
    if body.actor not in allowed:
        who = " or ".join(sorted(allowed))
        raise HTTPException(403, f"'{body.actor}' cannot perform '{body.action}'. Only {who} can. "
                                 "Decisions are made by people; the agent cannot approve or reject anything.")
    if body.action in {"approve", "submit_to_compliance"}:
        if case.route is None:
            raise HTTPException(409, "AI verification has not finished for this case yet, so it cannot be approved.")
        if case.stage >= 5:
            raise HTTPException(409, "This case has already been submitted to Compliance.")
    if body.action in {"send_back", "compliance_approve"} and case.stage != 5:
        raise HTTPException(409, "Compliance can act only after the KAM has submitted the case (stage 5).")


def _do_action(case_id: str, body: ActionRequest, session: Session):
    case = get_case(session, case_id)
    _authorise_action(case, body)
    _, title, detail, status, stage, tone = ACTIONS[body.action]
    if body.channel:
        detail += f" Channel: {body.channel}."
    if body.note:
        detail += f" Note: {body.note}"
    case.status = status
    if stage:
        case.stage = stage
    session.add(case)
    session.commit()
    audit(session, case_id, body.actor, title, detail, tone)
    if body.action == "voice" and (body.channel or "voice") == "voice":
        _hand_off_voice_chase(session, case)
    session.refresh(case)
    return Envelope(data=case_detail(session, case))


def _hand_off_voice_chase(session: Session, case: Case) -> None:
    """Trigger the n8n voice workflow. Never raises: the KAM's action is already recorded."""
    if not config.N8N_VOICE_WEBHOOK_URL:
        audit(session, case.id, "agent", "Voice call not placed",
              "Voice agent context is ready, but phone calling is not configured yet (N8N_VOICE_WEBHOOK_URL is empty).", "neutral")
        return
    try:
        r = httpx.post(config.N8N_VOICE_WEBHOOK_URL, json={"case_id": case.id}, timeout=5)
        r.raise_for_status()
        audit(session, case.id, "agent", "Voice chase handed to n8n", "n8n will place the call and report the outcome.", "ai")
    except httpx.HTTPError as e:
        audit(session, case.id, "agent", "Voice call not placed", f"n8n voice workflow unreachable: {e}"[:300], "warning")


@router.post("/cases/{case_id}/action", response_model=Envelope[CaseDetail])
def case_action(case_id: str, body: ActionRequest, session: Session = Depends(get_session)):
    return _do_action(case_id, body, session)


@router.post("/cases/{case_id}/actions", response_model=Envelope[CaseDetail], include_in_schema=False)
def case_actions_alias(case_id: str, body: ActionRequest, session: Session = Depends(get_session)):
    return _do_action(case_id, body, session)


# ---------- SSE ----------
def _events_since(case_id: str | None, last_id: int) -> list[dict]:
    with Session(engine) as s:
        q = select(AuditEvent).where(AuditEvent.id > last_id).order_by(AuditEvent.id).limit(100)
        if case_id:
            q = q.where(AuditEvent.case_id == case_id)
        return [{"id": e.id, "case_id": e.case_id, "ts": e.ts.isoformat(), "actor": e.actor, "action": e.action,
                 "detail": e.detail, "tone": e.tone, "doc_id": e.doc_id} for e in s.exec(q)]


def _latest_id(case_id: str | None) -> int:
    with Session(engine) as s:
        q = select(AuditEvent.id).order_by(AuditEvent.id.desc()).limit(1)
        if case_id:
            q = q.where(AuditEvent.case_id == case_id)
        return s.exec(q).first() or 0


async def _stream(case_id: str | None, after: int | None):
    last = _latest_id(case_id) if after is None else after   # no cursor -> only new events; replay via ?after=0
    yield "retry: 3000\n\n"
    idle = 0
    while True:
        events = await asyncio.to_thread(_events_since, case_id, last)
        for ev in events:
            last = ev["id"]
            yield f"id: {ev['id']}\nevent: audit\ndata: {json.dumps(ev)}\n\n"
        idle = 0 if events else idle + 1
        if idle and idle % 15 == 0:
            yield ": keep-alive\n\n"
        await asyncio.sleep(1)


_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.get("/cases/{case_id}/events")
async def case_events(case_id: str, after: int | None = Query(default=None)):
    with Session(engine) as s:
        get_case(s, case_id)
    return StreamingResponse(_stream(case_id, after), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.get("/events")
async def all_events(after: int | None = Query(default=None)):
    return StreamingResponse(_stream(None, after), media_type="text/event-stream", headers=_SSE_HEADERS)


# ---------- CRM form ----------
class OverrideBody(BaseModel):
    key: str
    value: str = Field(min_length=1, max_length=500)
    note: str | None = Field(default=None, max_length=300)


@router.get("/cases/{case_id}/crm-form")
def crm_form(case_id: str, session: Session = Depends(get_session)):
    return {"ok": True, "data": crm_builder.build(session, get_case(session, case_id))}


@router.post("/cases/{case_id}/crm-form/override")
def crm_override(case_id: str, body: OverrideBody, session: Session = Depends(get_session)):
    """KAM overrides one AI-filled field. The AI value stays on record; the audit trail shows both."""
    case = get_case(session, case_id)
    current = {f["key"]: f for s in crm_builder.build(session, case)["sections"] for f in s["fields"]}
    if body.key not in current:
        raise HTTPException(400, f"Unknown CRM field '{body.key}'")
    session.add(CrmOverride(case_id=case_id, key=body.key, value=body.value, note=body.note,
                            ai_value=current[body.key]["ai_value"]))
    session.commit()
    audit(session, case_id, "kam", "CRM field overridden",
          f"{current[body.key]['label']}: “{current[body.key]['value']}” → “{body.value}”" + (f" ({body.note})" if body.note else ""),
          "warning")
    return {"ok": True, "data": crm_builder.build(session, case)}


# ---------- cross-document checks ----------
@router.post("/cases/{case_id}/cross-check")
def cross_check_case(case_id: str, session: Session = Depends(get_session)):
    """n8n step: run the 10 deterministic checks, triage (AUTO/ASK/ESCALATE) and update the case.
    `issues` lists failed/warned checks, so the workflow's IF node can test `issues.length > 0`."""
    get_case(session, case_id)
    return {"ok": True, "data": cross_check.run(case_id)}


@router.get("/mock-registry/{case_id}")
def mock_registry_view(case_id: str):
    """The MOCK MCA / GST / penny-drop record the checks compare against (synthetic; clearly labelled)."""
    return {"ok": True, "data": mock_registry.lookup(case_id)}


# ---------- voice chase (Sarvam Samvaad agent; the call itself is placed by n8n) ----------
class VoiceResult(BaseModel):
    outcome: Literal["reached", "promised_upload", "callback_requested", "no_answer", "busy", "wrong_number", "failed", "not_configured"]
    summary: str | None = Field(default=None, max_length=2000)
    transcript: list[dict] | None = None
    call_id: str | None = Field(default=None, max_length=200)


@router.get("/cases/{case_id}/voice-chase/context")
def voice_chase_context(case_id: str, session: Session = Depends(get_session)):
    """Agent variables + Hindi opening line for this case. Only merchant-fixable items; escalations are held back."""
    return {"ok": True, "data": voice_agent.context(session, get_case(session, case_id))}


@router.post("/cases/{case_id}/voice-chase/result")
def voice_chase_result(case_id: str, body: VoiceResult, session: Session = Depends(get_session)):
    case = get_case(session, case_id)
    return {"ok": True, "data": voice_agent.record_result(session, case, body.outcome, body.summary, body.transcript, body.call_id)}


class VoiceMemoryResult(BaseModel):
    status: Literal["stored", "failed"]
    error: str | None = Field(default=None, max_length=1000)


@router.get("/voice-calls/{call_id}/memory-summary")
def voice_call_memory_summary(call_id: str, session: Session = Depends(get_session)):
    call = session.get(VoiceCall, call_id)
    if call is None:
        raise HTTPException(404, "Voice call not found")
    return {"ok": True, "data": voice_agent.memory_summary(session, call)}


@router.post("/voice-calls/{call_id}/memory/result")
def voice_call_memory_result(call_id: str, body: VoiceMemoryResult, session: Session = Depends(get_session)):
    call = session.get(VoiceCall, call_id)
    if call is None:
        raise HTTPException(404, "Voice call not found")
    return {"ok": True, "data": voice_agent.record_memory(session, call, body.status == "stored", body.error)}
