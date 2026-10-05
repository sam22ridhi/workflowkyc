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
    mcc: str | None = None                                # merchant category code, e.g. 5812 (restaurants): Drishti checks the counter photo against it
    ref_lat: float | None = None                          # where the shop should be: geocoded address, a demo reference, or a confirmed pin
    ref_lon: float | None = None
    ref_source: str | None = None                         # osm | demo | pin
    ref_label: str | None = None                          # the address the reference was derived from
    kind: str = "merchant"                                # merchant | investigation (a settlement investigation opened by the Settlement Agent)
    parent_case_id: str | None = None                     # investigations: the merchant case they belong to (same Cognee dataset)
    contact_name: str | None = None                       # person the voice agent asks for
    contact_phone: str | None = None                      # E.164, e.g. +919812345678 (used once phone calling is set up)
    stage: int = 2                                        # 1..10, see STAGES
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


class CpvSession(SQLModel, table=True):
    """Contact point verification by Drishti: a one-time capture link, the captures, and the verdict."""
    id: str = Field(primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True)
    token: str = Field(index=True, unique=True)
    status: str = "waiting"                               # waiting | captured | analysing | verified | needs_review | superseded
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime = Field(default_factory=lambda: utcnow() + timedelta(hours=24))
    captures: dict = Field(default_factory=dict, sa_column=Column(JSON))   # kind -> {path, sha256, lat, lon, accuracy_m, heading, client_ts, server_ts, ...}
    result: dict = Field(default_factory=dict, sa_column=Column(JSON))     # verdict, summary, checks[], distance_m, ocr, ...
    uploads: int = 0                                      # capture posts so far (rate limit)
    memory_status: str = "pending"                       # pending | stored | failed: the evidence in the case's Cognee dataset
    decided_by: str | None = None                         # set when a person decided a needs_review session
    updated_at: datetime = Field(default_factory=utcnow)


class VcipRecord(SQLModel, table=True):
    """V-CIP preparation: a Hindi pre-interview by the voice agent, then ONE human sign-off by an authorised official (RBI requires the human)."""
    id: str = Field(primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True, unique=True)
    status: str = "queued"                                # queued | interviewed | signed_off
    questions: list = Field(default_factory=list, sa_column=Column(JSON))   # [{id, kind, hi, en, expected}]
    transcript: list = Field(default_factory=list, sa_column=Column(JSON))
    call_id: str | None = None
    outcome: str | None = None                            # reached | no_answer | busy | failed ...
    summary: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    interviewed_at: datetime | None = None
    last_result_at: datetime | None = None                # last time a pre-interview call reported back (success or not)
    signed_off_by: str | None = None
    signed_off_at: datetime | None = None


class LedgerTxn(SQLModel, table=True):
    """One payment on a merchant's settlement ledger. SYNTHETIC in this demo (generated by app/finops/ledger.py); a real build reads the acquirer feed."""
    id: int | None = Field(default=None, primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True)
    ts: datetime = Field(index=True)
    amount: int                                           # whole rupees
    status: str = "captured"                              # captured | refund (merchant-initiated, expected) | chargeback (issuer debit, unexpected)
    channel: str = "UPI"                                  # UPI | CARD | WALLET
    terminal_id: str = "T-01"
    city: str = "Pune"
    payer_ref: str = ""                                   # masked: "CARD ••4417" / "VPA ••ab12"
    batch_id: str | None = None
    ref_txn_id: int | None = None                         # chargebacks: the original payment


class SettlementBatch(SQLModel, table=True):
    """What the merchant should receive (expected) and what the bank actually credited (actual)."""
    id: str = Field(primary_key=True)                     # e.g. B-20260930-A
    case_id: str = Field(foreign_key="case.id", index=True)
    day: str = Field(index=True)                          # IST calendar day, YYYY-MM-DD
    status: str = "paid"                                  # paid | held
    expected: int = 0                                     # captured - MDR - merchant refunds
    actual: int = 0                                       # credited: 0 when held; minus chargeback debits
    utr: str | None = None
    hold_reason: str | None = None


class Investigation(SQLModel, table=True):
    """What the Settlement Agent found and attached to the investigation case it opened."""
    id: str = Field(primary_key=True)                     # same as the investigation Case id
    merchant_case_id: str = Field(foreign_key="case.id", index=True)
    status: str = "open"                                  # open | resolved | dismissed
    window_from: str = ""
    window_to: str = ""
    detection: dict = Field(default_factory=dict, sa_column=Column(JSON))
    reconciliation: dict = Field(default_factory=dict, sa_column=Column(JSON))
    context: dict = Field(default_factory=dict, sa_column=Column(JSON))        # merchant twin answer (Cognee) + how it was obtained
    brief: str = ""
    brief_source: str = "template"                        # sarvam | template
    recommended: dict = Field(default_factory=dict, sa_column=Column(JSON))
    memory_status: str = "pending"                        # pending | stored | failed: the finding in the merchant's Cognee dataset
    created_at: datetime = Field(default_factory=utcnow)
    closed_by: str | None = None


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
    "Invited", "Docs Upload", "AI Verifying", "KAM Review", "Checker (Compliance)",
    "Contact Point Verification", "V-CIP Sign-off", "Bank Settlement Test", "e-Agreement Sign", "Live Unlimited",
]
STAGE_CPV, STAGE_VCIP = 6, 7
