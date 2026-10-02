"""SQLModel tables. App/transaction state lives here; Cognee is only the AI memory over the same documents."""
from datetime import datetime, timedelta, timezone

from sqlmodel import Column, Field, JSON, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Case(SQLModel, table=True):
    id: str = Field(primary_key=True)                     # e.g. KYB-20814
    slug: str                                             # cognee dataset suffix, e.g. sharma_foods
    merchant_name: str
    legal_name: str
    entity_type: str                                      # private_limited | llp | ...
    industry: str | None = None
    cin: str | None = None
    pan: str | None = None
    gstin: str | None = None
    registered_address: str | None = None                 # registered office, as stated in the merchant application
    operating_address: str | None = None                  # principal place of business if different; else registered_address
    contact_name: str | None = None                       # person the voice agent asks for
    contact_phone: str | None = None                      # E.164, e.g. +919812345678 (used once phone calling is set up)
    stage: int = 2                                        # 1..8, see STAGES
    account_status: str = "Live, capped · ₹50k"
    status: str = "docs_pending"                          # docs_pending|ai_verifying|awaiting_merchant|ready_for_review|needs_attention|live
    route: str | None = None                              # AUTO | ASK | ESCALATE (set by cross-check)
    summary: str | None = None
    seed_missing: str | None = None                       # demo-seeded cases only: comma list of documents shown as missing ("" = none)
    graph_status: str = "none"                            # Cognee knowledge graph: none | building | ready | failed
    graph_detail: str | None = None
    sla_due: datetime = Field(default_factory=lambda: utcnow() + timedelta(minutes=45))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


Case.application_operating_address = property(lambda self: self.operating_address or self.registered_address)  # type: ignore[attr-defined]


class Document(SQLModel, table=True):
    id: str = Field(primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True)
    slot: str | None = None                               # merchant UI slot it was uploaded into
    doc_type: str = "unknown"
    filename: str
    path: str
    mime: str
    size_bytes: int
    sha256: str
    status: str = "received"                              # received|extracting|extracted|needs_attention|error
    memory_status: str = "pending"                        # pending|stored|failed
    memory_error: str | None = None
    memory_data_ids: list | None = Field(default=None, sa_column=Column(JSON))   # Cognee data items for this document
    error: str | None = None
    page_count: int | None = None
    fields: dict | None = Field(default=None, sa_column=Column(JSON))   # {key: {value, confidence, page, box}}
    checks: list | None = Field(default=None, sa_column=Column(JSON))
    raw: dict | None = Field(default=None, sa_column=Column(JSON))      # raw Sarvam payload, kept for audit
    sarvam_job_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CheckResult(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True)
    check_id: str
    label: str
    status: str                                           # pass | fail | warn
    detail: str
    action: str | None = None                             # ask | escalate (for failed / warned checks)
    evidence: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class VoiceCall(SQLModel, table=True):
    """One voice chase attempt and its outcome (reported by n8n when Sarvam's call completes)."""
    id: str = Field(primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True)
    outcome: str                                          # reached | promised_upload | callback_requested | no_answer | busy | wrong_number | failed | not_configured
    summary: str | None = None
    transcript: list = Field(default_factory=list, sa_column=Column(JSON))   # [{role, text}]
    call_id: str | None = None                            # Sarvam interaction id
    memory_status: str = "pending"                        # pending | stored | failed | n/a (nothing to remember)
    memory_error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class AuditEvent(SQLModel, table=True):
    """Append-only trail. Also the SSE feed: clients stream rows with id > last seen."""
    id: int | None = Field(default=None, primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True)
    ts: datetime = Field(default_factory=utcnow)
    actor: str                                            # merchant | kam | compliance | agent
    action: str
    detail: str = ""
    tone: str = "neutral"                                 # neutral | ai | warning | success
    doc_id: str | None = None


class CrmOverride(SQLModel, table=True):
    """KAM override of an AI-filled CRM field. The AI value is kept for audit."""
    id: int | None = Field(default=None, primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True)
    key: str
    value: str
    ai_value: str | None = None
    note: str | None = None
    actor: str = "kam"
    created_at: datetime = Field(default_factory=utcnow)


STAGES = [
    "Invited", "Docs Upload", "AI Verifying", "KAM Review",
    "Checker (Compliance)", "Bank Settlement Test", "e-Agreement Sign", "Live Unlimited",
]
