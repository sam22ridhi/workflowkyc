"""DB rows -> API payloads. Kept out of the routes so both /api/cases and SSE can reuse them."""
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.doctypes import DOC_TYPES, ENTITY_LABELS, required_for
from app import voice_agent
from app.models import STAGES, AuditEvent, Case, CheckResult, Document, VoiceCall
from app.schemas_api import (
    CaseDetail, CaseRow, ChecklistItem, CheckOut, DocumentOut, FieldValue, Finding, Flag,
    LegacyDocument, StageItem, TimelineItem, VoiceCallOut,
)

PROCESSED = {"extracted", "needs_attention"}
STAGE_LABELS = {
    "docs_pending": "Documents Pending",
    "ai_verifying": "AI Verifying",
    "awaiting_merchant": "Awaiting Merchant Action",
    "needs_attention": "Escalated to KAM",
    "ready_for_review": "Ready for Review",
    "live": "Live / Approved",
}


def _iso(dt: datetime) -> str:
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def _ago(dt: datetime) -> str:
    secs = int((datetime.now(timezone.utc) - (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))).total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60} min ago"
    return f"{secs // 3600} h ago"


def doc_out(d: Document) -> DocumentOut:
    fields = None
    if d.fields:
        fields = {k: FieldValue(**v) if isinstance(v, dict) else FieldValue(value=v) for k, v in d.fields.items()}
    return DocumentOut(
        doc_id=d.id, case_id=d.case_id, slot=d.slot, doc_type=d.doc_type,
        doc_type_label=DOC_TYPES.get(d.doc_type, d.doc_type), filename=d.filename, mime=d.mime,
        size_bytes=d.size_bytes, sha256=d.sha256, status=d.status, memory_status=d.memory_status,
        memory_error=d.memory_error, error=d.error, page_count=d.page_count, fields=fields,
        checks=[CheckOut(**c) for c in d.checks] if d.checks else None,
        file_url=f"/api/documents/{d.id}/file", created_at=_iso(d.created_at), updated_at=_iso(d.updated_at),
    )


def _legacy_status(d: Document) -> str:
    return "processing" if d.status in {"received", "extracting"} else "received"


def sla_minutes(case: Case) -> int:
    due = case.sla_due if case.sla_due.tzinfo else case.sla_due.replace(tzinfo=timezone.utc)
    return max(0, int((due - datetime.now(timezone.utc)).total_seconds() // 60))


def _checks(session: Session, case_id: str) -> list[CheckResult]:
    return list(session.exec(select(CheckResult).where(CheckResult.case_id == case_id).order_by(CheckResult.id)))


def _legacy_case_status(case: Case) -> str:
    if case.status in {"needs_attention", "awaiting_merchant", "ready_for_review"}:
        return case.status
    return "awaiting_merchant" if case.status == "docs_pending" else "ready_for_review"


def checklist_for(case: Case, docs: list[Document]) -> list[ChecklistItem]:
    by_type: dict[str, Document] = {}
    for d in docs:
        by_type.setdefault(d.doc_type, d)
    seeded_missing = set(filter(None, (case.seed_missing or "").split(","))) if case.seed_missing is not None else None
    items = []
    for t in required_for(case.entity_type, case.industry):
        d = by_type.get(t)
        # demo-seeded cases have no files: required documents count as present unless the scenario says one is missing
        present = bool(d) or (seeded_missing is not None and t not in seeded_missing)
        items.append(ChecklistItem(doc_type=t, label=DOC_TYPES[t], status="uploaded" if present else "missing",
                                   doc_id=d.id if d else None))
    return items


def case_detail(session: Session, case: Case) -> CaseDetail:
    docs = list(session.exec(select(Document).where(Document.case_id == case.id).order_by(Document.created_at)))
    events = list(session.exec(select(AuditEvent).where(AuditEvent.case_id == case.id).order_by(AuditEvent.id)))
    checks = _checks(session, case.id)
    checklist = checklist_for(case, docs)
    uploaded = [c for c in checklist if c.status == "uploaded"]
    missing = [c for c in checklist if c.status == "missing"]

    findings = []
    for c in checks:
        if c.status != "fail":
            continue
        app_ev = next((e for e in c.evidence if e.get("source") in {"Merchant application", None} and not e.get("doc_id")), None)
        doc_ev = next((e for e in c.evidence if e.get("doc_id")), None)
        findings.append(Finding(
            id=c.check_id, title=c.label, status="exception", confidence=100,
            applicationValue=str((app_ev or {}).get("value") or ""),
            sourceValue=str((doc_ev or {}).get("value") or ""),
            explanation=c.detail,
            recommendedAction="Human review: escalate to a KAM decision" if c.action == "escalate"
            else "Ask the merchant to correct or re-upload"))
    processed = sum(1 for d in docs if d.status in PROCESSED)
    required = max(len(checklist), 1)

    return CaseDetail(
        id=case.id, merchantName=case.merchant_name, legalName=case.legal_name,
        entityType=ENTITY_LABELS.get(case.entity_type, case.entity_type), cin=case.cin, gstin=case.gstin,
        pan=case.pan, registeredAddress=case.registered_address, status=_legacy_case_status(case),
        accountStatus=case.account_status, stage=case.stage,
        stages=[StageItem(id=i + 1, label=l,
                          status="done" if i + 1 < case.stage else "current" if i + 1 == case.stage else "upcoming")
                for i, l in enumerate(STAGES)],
        route=case.route, summary=case.summary, graphStatus=case.graph_status,
        completion=int(100 * len(uploaded) / required) if checklist else 0,
        lastUpdated=_ago(case.updated_at),
        documents=[LegacyDocument(id=d.id, name=DOC_TYPES.get(d.doc_type, d.doc_type), kind=d.doc_type.upper(),
                                  status=_legacy_status(d),
                                  fieldsExtracted=sum(1 for v in (d.fields or {}).values()
                                                      if (v.get("value") if isinstance(v, dict) else v)),
                                  sourceLabel=f"{d.filename} · {d.status}") for d in docs]
                  + [LegacyDocument(id=m.doc_type, name=m.label, kind=m.doc_type.upper(), status="missing",
                                    fieldsExtracted=0, sourceLabel="Awaiting upload") for m in missing],
        checklist=checklist, uploaded=uploaded, missing=missing, findings=findings,
        checks=[CheckOut(id=c.check_id, label=c.label, status=c.status, detail=c.detail, evidence=c.evidence, action=c.action)
                for c in checks],
        voiceCalls=[VoiceCallOut(id=v.id, outcome=v.outcome, title=voice_agent.OUTCOME_TITLES[v.outcome][0], summary=v.summary,
                                 transcript=v.transcript or [], callId=v.call_id, memoryStatus=v.memory_status,
                                 timestamp=v.created_at.strftime("%d %b %H:%M"))
                    for v in session.exec(select(VoiceCall).where(VoiceCall.case_id == case.id).order_by(VoiceCall.created_at.desc()))],
        timeline=[TimelineItem(id=str(e.id), timestamp=e.ts.strftime("%H:%M:%S"), title=e.action, detail=e.detail,
                               tone=e.tone, actor=e.actor, ts=_iso(e.ts)) for e in events],
    )


def case_row(session: Session, case: Case) -> CaseRow:
    docs = list(session.exec(select(Document).where(Document.case_id == case.id)))
    checks = _checks(session, case.id)
    checklist = checklist_for(case, docs)
    flags: list[Flag] = []
    for c in checks:
        if c.status == "fail":
            flags.append(Flag(label=c.label, severity="critical"))
        elif c.status == "warn":
            flags.append(Flag(label=c.label, severity="warning"))
    if not flags and checks:
        flags.append(Flag(label="No issues", severity="ok"))
    confs = [f["confidence"] for d in docs for f in (d.fields or {}).values()
             if isinstance(f, dict) and isinstance(f.get("confidence"), (int, float))]
    mins = sla_minutes(case)
    return CaseRow(
        id=case.id, merchantName=case.merchant_name, legalName=case.legal_name,
        entityType=ENTITY_LABELS.get(case.entity_type, case.entity_type),
        stage=STAGE_LABELS.get(case.status, "Documents Pending"), stageNumber=case.stage,
        accountStatus=case.account_status, route=case.route, flags=flags,
        aiConfidence=int(sum(confs) / len(confs)) if confs else 0, slaMinutes=mins,
        isUrgent=mins < 20 or case.route == "ESCALATE",
        docProgress={"uploaded": sum(1 for c in checklist if c.status == "uploaded"), "required": len(checklist),
                     "processed": (sum(1 for c in checklist if c.status == "uploaded") if case.seed_missing is not None and not docs
                                   else sum(1 for d in docs if d.status in PROCESSED))},
        lastUpdated=_ago(case.updated_at),
    )
