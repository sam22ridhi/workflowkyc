"""KAM housekeeping for the demo: delete one submitted file, or reset a whole demo case so the story can be shown again.

Deleting a file keeps the case honest: the checks are re-run on what is left (or the case goes back to "documents pending" when nothing is left),
the file leaves the disk, and the copy in the merchant twin (Cognee) is removed when it can be. Every step is written to the timeline.
"""
import logging
import shutil
from pathlib import Path

from fastapi import HTTPException
from sqlmodel import Session, select

from app import config
from app.checks import cross_check
from app.db import audit
from app.memory import get_store
from app.memory.base import MemoryUnavailable
from app.models import AuditEvent, Case, CheckResult, CpvSession, CrmOverride, Document, VcipRecord, VoiceCall, utcnow

log = logging.getLogger("karyakarta.admin")


def _dataset(case: Case) -> str:
    return f"case_{case.slug}"


def _remove_file(path: str) -> None:
    p = Path(path).resolve()
    root = Path(config.STORAGE_DIR).resolve()
    if root in p.parents and p.exists():
        p.unlink()


def _forget_in_memory(case: Case, doc: Document) -> str:
    """Best effort: remove the document's items from the merchant twin. Returns a sentence for the timeline."""
    if doc.memory_status != "stored":
        return "It had not been stored in the merchant twin."
    ids = list(doc.memory_data_ids or [])
    if not ids:
        return "Its copy in the merchant twin could not be matched to an item, so it stays there until the case memory is reset."
    try:
        n = get_store().delete_data(_dataset(case), ids)
        return f"Removed {n} item(s) from the merchant twin (Cognee); the graph forgets them when it is next rebuilt."
    except (MemoryUnavailable, AttributeError) as e:
        return f"Could not remove it from the merchant twin ({str(e)[:120]}); it stays there until the case memory is reset."


def delete_document(session: Session, doc: Document, actor: str) -> dict:
    if actor != "kam":
        raise HTTPException(403, f"'{actor}' cannot delete a submitted file. Only the KAM can.")
    case = session.get(Case, doc.case_id)
    if case.kind != "merchant" or case.stage >= 5:
        raise HTTPException(409, "This case has already been submitted to Compliance, so its files are locked. Send it back to the KAM first.")
    filename, doc_id, case_id = doc.filename, doc.id, case.id
    memory_note = _forget_in_memory(case, doc)
    _remove_file(doc.path)
    session.delete(doc)
    session.commit()
    audit(session, case_id, "kam", "Document deleted by the KAM", f"{filename} was removed from the case. {memory_note}", "warning")

    remaining = list(session.exec(select(Document).where(Document.case_id == case_id)))
    if remaining:
        result = cross_check.run(case_id)
        outcome = f"The checks were re-run on the {len(remaining)} remaining document(s): route {result['route']}."
    else:
        for row in session.exec(select(CheckResult).where(CheckResult.case_id == case_id)):
            session.delete(row)
        case = session.get(Case, case_id)
        case.route, case.summary, case.status, case.stage, case.graph_status, case.graph_detail = None, None, "docs_pending", 2, "none", None
        case.updated_at = utcnow()
        session.add(case)
        session.commit()
        audit(session, case_id, "agent", "No documents left", "The case is back to documents pending; the checks were cleared.", "neutral")
        outcome = "No documents are left, so the case is back to documents pending."
    return {"deleted": filename, "doc_id": doc_id, "memory": memory_note, "remaining": len(remaining), "outcome": outcome}


def reset_case(session: Session, case: Case) -> dict:
    """DEMO ONLY: put an onboarding case back to the state it had when seeded (no documents, no checks, no calls, no verification), memory included."""
    from app.seed_cases import CASES, _PRECOMPUTED, _seed_precomputed_results

    spec = next((c for c in CASES if c["id"] == case.id), None)
    if case.kind != "merchant" or spec is None:
        raise HTTPException(409, "Only the seeded onboarding cases can be reset.")
    case_id = case.id
    for model in (CheckResult, VoiceCall, CpvSession, VcipRecord, CrmOverride, Document, AuditEvent):
        for row in list(session.exec(select(model).where(model.case_id == case_id))):
            session.delete(row)
    session.commit()
    folder = (Path(config.STORAGE_DIR) / case_id).resolve()
    if Path(config.STORAGE_DIR).resolve() in folder.parents and folder.exists():
        shutil.rmtree(folder, ignore_errors=True)

    case = session.get(Case, case_id)
    case.stage, case.status, case.route, case.summary = spec["stage"], spec["status"], None, None
    case.account_status, case.graph_status, case.graph_detail = spec["account_status"], "none", None
    case.ref_lat = case.ref_lon = case.ref_source = case.ref_label = None
    case.seed_missing = None
    case.contact_phone = spec.get("contact_phone")
    case.sla_due = utcnow() + __import__("datetime").timedelta(minutes=spec["sla"])
    case.updated_at = utcnow()
    session.add(case)
    session.commit()
    if case_id in _PRECOMPUTED:
        _seed_precomputed_results(session, only={case_id})
    audit(session, case_id, "merchant", "Application submitted", "Merchant submitted onboarding details (Stage 1 live, ₹50k cap).", "neutral")
    try:
        memory = "The merchant twin (Cognee dataset) was deleted." if get_store().delete_dataset(_dataset(case)) else "There was no merchant twin to delete."
    except (MemoryUnavailable, AttributeError) as e:
        memory = f"The merchant twin could not be deleted ({str(e)[:120]}); it will be extended by the next upload."
    audit(session, case_id, "agent", "Demo reset", f"The case was put back to its starting state. {memory}", "neutral")
    return {"case_id": case_id, "memory": memory}
