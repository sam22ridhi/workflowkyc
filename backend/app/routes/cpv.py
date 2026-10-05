"""Contact point verification (Drishti): the public capture link, and the case-facing views n8n and the KAM use."""
import logging
from typing import Literal

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session

from app import config
from app.db import audit, get_session
from app.drishti import service
from app.models import Case, CpvSession

router = APIRouter(prefix="/api")
log = logging.getLogger("karyakarta.cpv")


def _case(session: Session, case_id: str) -> Case:
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    return case


def _guard(fn, *a, **k):
    try:
        return fn(*a, **k)
    except service.CpvError as e:
        raise HTTPException(e.status, str(e)) from e


# ---------------------------------------------------------------- public: the merchant's capture page
@router.get("/cpv/{token}")
def capture_state(token: str, session: Session = Depends(get_session)):
    """What the capture page needs. Nothing sensitive: the business name, what to capture and what has been captured."""
    s = _guard(service.by_token, session, token)
    case = _case(session, s.case_id)
    v = service.view(s)
    return {"ok": True, "data": {"merchantName": case.merchant_name, "status": s.status, "required": v["required"], "optional": v["optional"],
                                 "captured": v["captured"], "expiresAt": v["expiresAt"], "verdict": v["verdict"], "summary": v["summary"],
                                 "maxAccuracyM": config.CPV_MAX_ACCURACY_M, "demoUpload": config.CPV_ALLOW_DEMO_REFERENCE}}


@router.post("/cpv/{token}/capture")
async def capture(token: str, kind: str = Form(...), lat: float = Form(...), lon: float = Form(...), accuracy_m: float = Form(...),
                  client_ts: str = Form(...), source: str = Form("camera_stream"), heading: str | None = Form(None),
                  image: UploadFile = File(...), session: Session = Depends(get_session)):
    s = _guard(service.by_token, session, token)
    case = _case(session, s.case_id)
    data = await image.read()
    _guard(service.store_capture, session, s, case, kind, data, lat=lat, lon=lon, accuracy_m=accuracy_m, heading=heading, client_ts=client_ts, source=source)
    return {"ok": True, "data": {"captured": list((s.captures or {}).keys())}}


@router.post("/cpv/{token}/submit")
def submit(token: str, background: BackgroundTasks, session: Session = Depends(get_session)):
    s = _guard(service.by_token, session, token)
    case = _case(session, s.case_id)
    _guard(service.submit, session, s, case)
    _trigger_analysis(case.id, s.id, background)
    return {"ok": True, "data": {"status": "captured"}}


def _trigger_analysis(case_id: str, session_id: str, background: BackgroundTasks) -> None:
    """Hand the analysis to n8n when it is configured, else (or if n8n cannot be reached) run it here."""
    url = config.N8N_CPV_WEBHOOK_URL.replace("karyakarta-cpv-start", "karyakarta-cpv-captured") if config.N8N_CPV_WEBHOOK_URL else ""
    if url:
        try:
            httpx.post(url, json={"case_id": case_id, "session_id": session_id}, timeout=5).raise_for_status()
            return
        except httpx.HTTPError as e:
            log.warning("n8n CPV webhook failed (%s); analysing in-process", e)
    background.add_task(_analyse_quietly, session_id)


def _analyse_quietly(session_id: str) -> None:
    try:
        service.analyse(session_id)
    except Exception:  # noqa: BLE001
        log.exception("Drishti analysis failed for %s", session_id)


# ---------------------------------------------------------------- case-facing
@router.get("/cases/{case_id}/cpv")
def case_cpv(case_id: str, session: Session = Depends(get_session)):
    _case(session, case_id)
    return {"ok": True, "data": service.view(service.active_session(session, case_id))}


@router.post("/cases/{case_id}/cpv/link")
def case_link(case_id: str, session: Session = Depends(get_session)):
    """The current capture link (creating one if needed). Called by n8n when verification opens."""
    case = _case(session, case_id)
    s = service.ensure_session(session, case)
    return {"ok": True, "data": service.view(s)}


@router.post("/cases/{case_id}/cpv/analyse")
def case_analyse(case_id: str, session: Session = Depends(get_session)):
    """Run Drishti on the captured photos (called by n8n after the merchant submits)."""
    _case(session, case_id)
    s = service.active_session(session, case_id)
    if s is None or s.status not in {"captured", "analysing", "needs_review", "verified"}:
        raise HTTPException(409, "The merchant has not submitted the photos yet.")
    result = _guard(service.analyse, s.id)
    session.refresh(s)
    return {"ok": True, "data": {**service.view(s), "result": result}}


@router.get("/cases/{case_id}/cpv/images/{kind}")
def case_image(case_id: str, kind: str, session: Session = Depends(get_session)):
    _case(session, case_id)
    s = service.active_session(session, case_id)
    cap = ((s.captures if s else None) or {}).get(kind)
    if not cap:
        raise HTTPException(404, "No such photo")
    return FileResponse(cap["path"], media_type="image/jpeg")


class CpvMemoryResult(BaseModel):
    status: Literal["stored", "failed"]
    error: str | None = Field(default=None, max_length=1000)


@router.get("/cases/{case_id}/cpv/memory-summary")
def cpv_memory_summary(case_id: str, session: Session = Depends(get_session)):
    case = _case(session, case_id)
    s = service.active_session(session, case_id)
    if s is None or not s.result:
        raise HTTPException(409, "Drishti has not analysed this case yet.")
    return {"ok": True, "data": service.memory_summary(session, case, s)}


@router.post("/cases/{case_id}/cpv/memory/result")
def cpv_memory_result(case_id: str, body: CpvMemoryResult, session: Session = Depends(get_session)):
    _case(session, case_id)
    current = service.active_session(session, case_id)
    if current is not None:
        current.memory_status = body.status
        session.add(current)
        session.commit()
    if body.status == "stored":
        audit(session, case_id, "agent", "Shop verification stored in Cognee memory", "The verification evidence can now be searched with Ask this case.", "ai")
    else:
        audit(session, case_id, "agent", "Memory unavailable", f"{(body.error or 'Cognee reported an error')[:300]}. The verification itself is unaffected.", "warning")
    return {"ok": True, "data": {"status": body.status}}


class DemoReference(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    label: str | None = Field(default=None, max_length=200)


@router.post("/cases/{case_id}/cpv/demo-reference")
def demo_reference(case_id: str, body: DemoReference, session: Session = Depends(get_session)):
    """DEMO ONLY: say where the shop 'is', so a synthetic address can be tested from wherever the demo runs.
    Off unless CPV_ALLOW_DEMO_REFERENCE=true, and every use is written to the timeline."""
    if not config.CPV_ALLOW_DEMO_REFERENCE:
        raise HTTPException(403, "Setting a demo reference point is disabled. Set CPV_ALLOW_DEMO_REFERENCE=true to allow it for a demo.")
    case = _case(session, case_id)
    case.ref_lat, case.ref_lon, case.ref_source, case.ref_label = body.lat, body.lon, "demo", body.label or "demo reference point"
    session.add(case)
    session.commit()
    audit(session, case_id, "kam", "Demo reference point set", f"The shop's reference location was set to {body.lat:.5f}, {body.lon:.5f} for a demo. It is not a geocoded address.", "warning")
    return {"ok": True, "data": {"lat": body.lat, "lon": body.lon, "source": "demo"}}
