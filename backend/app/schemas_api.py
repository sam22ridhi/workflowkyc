"""Response models.

Naming: case-level payloads keep the frontend's existing camelCase contract (merchantName, sourceLabel...).
Document / check / memory payloads are new and use snake_case, as in the API spec.
"""
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    ok: bool = True
    data: T


# ---------- documents ----------
class FieldValue(BaseModel):
    value: Any = None
    confidence: float | None = None            # 0-100
    page: int | None = None                    # 1-based
    box: dict | None = None                    # {page,x,y,w,h} 0-1 relative, only when really located
    box_source: Literal["sarvam", "pdf_text_layer", "digitise", "none"] = "none"
    box_precision: Literal["block", "table"] = "block"   # "table": Sarvam only localises the whole table block
    boxes: list[dict] | None = None                      # list fields: one box per row, {row,page,x,y,w,h}
    rows: list[dict] | None = None                       # list fields: per-row, per-leaf {confidence,page}


class CheckOut(BaseModel):
    id: str
    label: str
    status: Literal["pass", "fail", "warn", "skip"]
    detail: str
    evidence: list[dict] = Field(default_factory=list)
    action: Literal["ask", "escalate"] | None = None


class DocumentOut(BaseModel):
    doc_id: str
    case_id: str
    slot: str | None
    doc_type: str
    doc_type_label: str
    filename: str
    mime: str
    size_bytes: int
    sha256: str
    status: str
    memory_status: str
    memory_error: str | None = None
    error: str | None = None
    page_count: int | None = None
    fields: dict[str, FieldValue] | None = None
    checks: list[CheckOut] | None = None
    file_url: str
    created_at: str
    updated_at: str


class ExtractOut(BaseModel):          # what n8n gets back from POST /documents/{id}/extract
    doc_id: str
    status: str
    checks_passed: bool                 # n8n's IF node can branch on this
    boxes: Literal["ready", "pending"]
    seconds: float
    document: DocumentOut | None = None


class RejectedFile(BaseModel):
    filename: str
    reason: str


class UploadAccepted(BaseModel):
    case_id: str
    doc_ids: list[str]
    documents: list[DocumentOut]
    rejected: list[RejectedFile] = Field(default_factory=list)
    pipeline: Literal["queued", "none"] = "none"   # dispatch happens after the 202; see the audit trail for which path ran


class StatusUpdate(BaseModel):
    status: Literal["received", "extracting", "extracted", "needs_attention", "error"]
    message: str | None = Field(default=None, max_length=10000)   # n8n error text can be long; stored truncated


class DocTypeUpdate(BaseModel):
    doc_type: str


# ---------- cases ----------
class LegacyDocument(BaseModel):          # shape the existing frontend already consumes
    id: str
    name: str
    kind: str
    status: Literal["received", "missing", "processing"]
    fieldsExtracted: int
    sourceLabel: str


class ChecklistItem(BaseModel):
    doc_type: str
    label: str
    status: Literal["uploaded", "missing"]
    doc_id: str | None = None


class TimelineItem(BaseModel):
    id: str
    timestamp: str
    title: str
    detail: str
    tone: Literal["neutral", "ai", "warning", "success"]
    actor: str
    ts: str


class StageItem(BaseModel):
    id: int
    label: str
    status: Literal["done", "current", "upcoming"]


class Finding(BaseModel):
    id: str
    title: str
    status: Literal["exception", "verified"]
    confidence: int
    applicationValue: str
    sourceValue: str
    explanation: str
    recommendedAction: str


class Flag(BaseModel):
    label: str
    severity: Literal["info", "warning", "critical", "ok"]


class CaseRow(BaseModel):                  # one row of the KAM pipeline table
    id: str
    merchantName: str
    legalName: str
    entityType: str
    stage: str                             # frontend CasePipelineItem.stage labels
    stageNumber: int
    accountStatus: str
    route: Literal["AUTO", "ASK", "ESCALATE"] | None
    flags: list[Flag]
    aiConfidence: int
    slaMinutes: int
    isUrgent: bool
    docProgress: dict[str, int]            # {uploaded, required, processed}
    lastUpdated: str


class Kpis(BaseModel):
    totalOpen: int
    newThisWeek: int
    pendingAiVerification: int
    awaitingMerchant: int
    readyForSubmission: int
    escalations: int


class CaseList(BaseModel):
    kpis: Kpis
    items: list[CaseRow]


class VoiceCallOut(BaseModel):
    id: str
    outcome: str
    title: str
    summary: str | None
    transcript: list[dict]
    callId: str | None
    memoryStatus: str
    timestamp: str


class CaseDetail(BaseModel):
    id: str
    merchantName: str
    legalName: str
    entityType: str
    cin: str | None
    gstin: str | None
    pan: str | None
    registeredAddress: str | None
    status: Literal["needs_attention", "awaiting_merchant", "ready_for_review"]
    accountStatus: str
    stage: int
    stages: list[StageItem]
    route: Literal["AUTO", "ASK", "ESCALATE"] | None
    summary: str | None
    graphStatus: Literal["none", "building", "ready", "failed"] = "none"
    completion: int
    lastUpdated: str
    documents: list[LegacyDocument]
    checklist: list[ChecklistItem]
    uploaded: list[ChecklistItem]
    missing: list[ChecklistItem]
    findings: list[Finding]
    checks: list[CheckOut]
    timeline: list[TimelineItem]
    voiceCalls: list[VoiceCallOut] = Field(default_factory=list)


class ActionRequest(BaseModel):
    action: Literal["request", "voice", "approve", "submit_to_compliance", "send_back", "compliance_approve"]
    channel: Literal["voice", "whatsapp", "email"] | None = None
    note: str | None = Field(default=None, max_length=500)
    actor: Literal["merchant", "kam", "compliance", "agent"] = "kam"
