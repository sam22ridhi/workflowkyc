"""Settlement Agent endpoints. n8n (Sutradhar) calls monitor / reconcile / investigate / memory-summary; the Settlements tab calls the view and scan."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app import config
from app.db import audit, get_session
from app.finops import ledger, service
from app.models import Case

router = APIRouter(prefix="/api")


def _case(session: Session, case_id: str) -> Case:
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    return case


def _demo_only() -> None:
    if not config.CPV_ALLOW_DEMO_REFERENCE:
        raise HTTPException(403, "Demo controls are disabled. Set CPV_ALLOW_DEMO_REFERENCE=true in backend/.env to allow them for a demo.")


@router.get("/cases/{case_id}/settlements")
def settlements_view(case_id: str, session: Session = Depends(get_session)):
    return {"ok": True, "data": service.view(session, _case(session, case_id))}


@router.post("/cases/{case_id}/settlements/scan")
def settlements_scan(case_id: str, background: BackgroundTasks, session: Session = Depends(get_session)):
    """Start the agent's chain for this merchant: through n8n when configured, otherwise in the backend."""
    m = service.merchant_of(session, _case(session, case_id))
    audit(session, m.id, "kam", "Settlement check requested", "Started the Settlement Agent for this merchant.", "ai")
    via = service.trigger(m.id)
    if via == "in-process":
        background.add_task(service.run_pipeline, m.id)
    return {"ok": True, "data": {"status": "started", "via": via, "case_id": m.id}}


# ---- the steps n8n runs one by one (each is also used by the in-process fallback)
@router.post("/cases/{case_id}/settlements/monitor")
def step_monitor(case_id: str, session: Session = Depends(get_session)):
    return {"ok": True, "data": service.monitor(session, _case(session, case_id))}


@router.post("/cases/{case_id}/settlements/reconcile")
def step_reconcile(case_id: str, session: Session = Depends(get_session)):
    return {"ok": True, "data": service.do_reconcile(session, _case(session, case_id))}


class InvestigateBody(BaseModel):
    context: object | None = None          # what the Cognee recall node returned (any shape); None = the backend asks Cognee itself


@router.post("/cases/{case_id}/settlements/investigate")
def step_investigate(case_id: str, body: InvestigateBody, session: Session = Depends(get_session)):
    return {"ok": True, "data": service.investigate(session, _case(session, case_id), body.context, "n8n recall")}


@router.get("/settlements/{inv_id}/memory-summary")
def memory_summary(inv_id: str, session: Session = Depends(get_session)):
    if session.get(service.Investigation, inv_id) is None:
        raise HTTPException(404, "Investigation not found")
    return {"ok": True, "data": service.memory_summary(session, inv_id)}


class MemoryResult(BaseModel):
    status: str
    error: str | None = None


@router.post("/settlements/{inv_id}/memory/result")
def memory_result(inv_id: str, body: MemoryResult, session: Session = Depends(get_session)):
    if session.get(service.Investigation, inv_id) is None:
        raise HTTPException(404, "Investigation not found")
    return {"ok": True, "data": service.record_memory_result(session, inv_id, body.status == "stored", body.error)}


# ---- demo controls (synthetic data only)
@router.post("/cases/{case_id}/settlements/demo/spike")
def demo_spike(case_id: str, session: Session = Depends(get_session)):
    """DEMO ONLY: inject a 48-hour spike (about ₹15 lakh) and a settlement mismatch into the synthetic ledger, then run the agent."""
    _demo_only()
    m = service.merchant_of(session, _case(session, case_id))
    if m.stage < 10 or m.kind != "merchant":
        raise HTTPException(409, "Only an activated merchant has a settlement ledger.")
    out = ledger.generate(session, m.id, spike=True)
    audit(session, m.id, "agent", "Demo: spike injected", f"A synthetic 48-hour spike and settlement mismatch were added to the ledger ({out['transactions']} payments in total). Nothing real happened.", "warning")
    return {"ok": True, "data": out}


@router.post("/cases/{case_id}/settlements/demo/reset")
def demo_reset(case_id: str, session: Session = Depends(get_session)):
    """DEMO ONLY: back to a healthy ledger and close any open investigation, so the demo can be run again."""
    _demo_only()
    m = service.merchant_of(session, _case(session, case_id))
    if m.stage < 10 or m.kind != "merchant":
        raise HTTPException(409, "Only an activated merchant has a settlement ledger.")
    from sqlmodel import select
    for inv in session.exec(select(service.Investigation).where(service.Investigation.merchant_case_id == m.id, service.Investigation.status == "open")):
        inv.status, inv.closed_by = "dismissed", "demo reset"
        session.add(inv)
        c = session.get(Case, inv.id)
        if c:
            c.status = "closed"
            session.add(c)
    session.commit()
    out = ledger.generate(session, m.id, spike=False)
    audit(session, m.id, "agent", "Demo: ledger reset", "The synthetic ledger is healthy again and open investigations were closed.", "neutral")
    return {"ok": True, "data": out}
