from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="KARYAKARTA API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CaseStatus = Literal["needs_attention", "awaiting_merchant", "ready_for_review"]
DocumentStatus = Literal["received", "missing", "processing"]
FindingStatus = Literal["exception", "verified"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_case() -> dict[str, Any]:
    return {
        "id": "KYB-20814",
        "merchantName": "Sharma Foods",
        "legalName": "Sharma Foods Private Limited",
        "cin": "U74999MH2021PTC123456",
        "gstin": "27AABCS4821Q1Z7",
        "pan": "AABCS4821Q",
        "registeredAddress": "12 MG Road, Mumbai",
        "status": "needs_attention",
        "completion": 72,
        "lastUpdated": "12 min ago",
        "documents": [
            {"id": "coi", "name": "Certificate of Incorporation", "kind": "COI", "status": "received", "fieldsExtracted": 6, "sourceLabel": "COI.pdf · Page 1"},
            {"id": "pan", "name": "Company PAN", "kind": "PAN", "status": "received", "fieldsExtracted": 4, "sourceLabel": "Company_PAN.pdf · Page 1"},
            {"id": "gst", "name": "GST Certificate", "kind": "GST", "status": "received", "fieldsExtracted": 8, "sourceLabel": "GST_Certificate.pdf · Page 1"},
            {"id": "board", "name": "Board Resolution", "kind": "BOARD", "status": "received", "fieldsExtracted": 5, "sourceLabel": "Board_Resolution.pdf · Page 2"},
            {"id": "cheque", "name": "Cancelled Cheque", "kind": "BANK", "status": "missing", "fieldsExtracted": 0, "sourceLabel": "Awaiting upload"},
            {"id": "address", "name": "Address Proof", "kind": "ADDRESS", "status": "missing", "fieldsExtracted": 0, "sourceLabel": "Awaiting correction"},
        ],
        "findings": [{
            "id": "address-drift",
            "title": "Address mismatch",
            "status": "exception",
            "confidence": 91,
            "applicationValue": "12 MG Road, Mumbai",
            "sourceValue": "12 Mahatma Gandhi Marg, Navi Mumbai",
            "explanation": "The registered address differs between the submitted application and GST Certificate.",
            "recommendedAction": "Request corrected address proof",
        }],
        "timeline": [
            {"id": "submitted", "timestamp": "09:12:04", "title": "Application submitted", "detail": "Merchant submitted onboarding details and initial documents.", "tone": "neutral"},
            {"id": "parsed", "timestamp": "09:12:19", "title": "GST Certificate parsed", "detail": "AI extracted 8 fields with high confidence.", "tone": "ai"},
            {"id": "contradiction", "timestamp": "09:12:26", "title": "Contradiction detected", "detail": "Address mismatch found across application and GST Certificate.", "tone": "warning"},
        ],
    }


case_store: dict[str, dict[str, Any]] = {"KYB-20814": seed_case()}


class ActionRequest(BaseModel):
    action: Literal["request", "voice", "approve"]
    channel: Literal["voice", "whatsapp", "email"] | None = None
    note: str | None = Field(default=None, max_length=500)


class CaseResponse(BaseModel):
    ok: bool = True
    data: dict[str, Any]


def get_case(case_id: str) -> dict[str, Any]:
    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def add_event(case: dict[str, Any], title: str, detail: str, tone: str) -> None:
    case["lastUpdated"] = "just now"
    case["timeline"].append({"id": f"event-{len(case['timeline']) + 1}", "timestamp": datetime.now().strftime("%H:%M:%S"), "title": title, "detail": detail, "tone": tone})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/cases", response_model=CaseResponse)
def list_cases() -> CaseResponse:
    return CaseResponse(data={"items": list(case_store.values())})


@app.get("/api/cases/{case_id}", response_model=CaseResponse)
def read_case(case_id: str) -> CaseResponse:
    return CaseResponse(data=deepcopy(get_case(case_id)))


@app.post("/api/cases/{case_id}/documents", response_model=CaseResponse)
def upload_document(case_id: str, kind: str = Form(...), file: UploadFile = File(...)) -> CaseResponse:
    case = get_case(case_id)
    document = next((item for item in case["documents"] if item["id"] == kind), None)
    if document is None:
        raise HTTPException(status_code=400, detail="Unsupported document kind")
    document.update({"status": "received", "fieldsExtracted": 4, "sourceLabel": f"{file.filename or document['name'] } · Page 1"})
    is_address = kind == "address"
    case["completion"] = 100 if is_address else min(88, case["completion"] + 10)
    add_event(case, "Merchant re-uploaded", f"{document['name']} was added to the case.", "neutral")
    if is_address:
        for finding in case["findings"]:
            finding["status"] = "verified"
        case["status"] = "ready_for_review"
        add_event(case, "AI re-verified", "Corrected address proof now matches the submitted application.", "success")
    return CaseResponse(data=deepcopy(case))


@app.post("/api/cases/{case_id}/actions", response_model=CaseResponse)
def case_action(case_id: str, payload: ActionRequest) -> CaseResponse:
    case = get_case(case_id)
    if payload.action == "voice":
        case["status"] = "awaiting_merchant"
        add_event(case, "KAM chased via Voice", "Voice agent requested corrected address proof from the merchant.", "ai")
    elif payload.action == "request":
        case["status"] = "awaiting_merchant"
        add_event(case, "Information requested", "KAM requested corrected address proof from the merchant.", "neutral")
    else:
        case["status"] = "ready_for_review"
        add_event(case, "KAM approved application", "All AI findings are verified and the case is ready to move forward.", "success")
    return CaseResponse(data=deepcopy(case))


@app.get("/api/cases/{case_id}/timeline", response_model=CaseResponse)
def case_timeline(case_id: str) -> CaseResponse:
    case = get_case(case_id)
    return CaseResponse(data={"case_id": case_id, "items": deepcopy(case["timeline"])})
