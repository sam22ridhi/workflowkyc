from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app import memory_service
from app.db import get_session
from app.memory import MemoryUnavailable, get_store
from app.models import Case, Document

router = APIRouter(prefix="/api")


class AskBody(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@router.post("/documents/{doc_id}/memory")
def store_document(doc_id: str, session: Session = Depends(get_session)):
    """n8n step 'Cognee: store document'. Always 200 once the document exists: a Cognee outage is reported as
    memory_status='failed' so the workflow keeps going (extraction and checks never depend on memory)."""
    if session.get(Document, doc_id) is None:
        raise HTTPException(404, "Document not found")
    return {"ok": True, "data": memory_service.store_document(doc_id)}


@router.post("/cases/{case_id}/memory/cognify")
def cognify(case_id: str, session: Session = Depends(get_session)):
    """n8n step 'Cognee: build knowledge graph' (once per batch)."""
    if session.get(Case, case_id) is None:
        raise HTTPException(404, "Case not found")
    return {"ok": True, "data": memory_service.cognify_case(case_id)}


@router.post("/cases/{case_id}/ask")
def ask(case_id: str, body: AskBody, session: Session = Depends(get_session)):
    if session.get(Case, case_id) is None:
        raise HTTPException(404, "Case not found")
    try:
        return {"ok": True, "data": memory_service.ask(case_id, body.question)}
    except MemoryUnavailable as e:
        raise HTTPException(503, f"Case memory is unavailable right now: {e}")


@router.get("/cases/{case_id}/memory")
def memory_status(case_id: str, session: Session = Depends(get_session)):
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    docs = session.query(Document).filter(Document.case_id == case_id).all()
    counts = {s: sum(1 for d in docs if d.memory_status == s) for s in ("pending", "stored", "failed")}
    return {"ok": True, "data": {"case_id": case_id, "dataset": memory_service.dataset_name(case), "graph_status": case.graph_status,
                                 "detail": case.graph_detail, "documents": counts, "backend": get_store().health()}}


# ---------- report-back endpoints for n8n's native Cognee nodes ----------
class MemoryResult(BaseModel):
    status: Literal["stored", "failed"]
    error: str | None = Field(default=None, max_length=1000)
    response: Any = None            # the Cognee node's output, used to pick up data_ids


class GraphResult(BaseModel):
    status: Literal["completed", "failed"]
    detail: str | None = Field(default=None, max_length=1000)


@router.get("/documents/{doc_id}/memory-summary")
def memory_summary(doc_id: str, session: Session = Depends(get_session)):
    """The text n8n's 'Cognee: store document' node adds to the case dataset (extracted facts + checks)."""
    if session.get(Document, doc_id) is None:
        raise HTTPException(404, "Document not found")
    return {"ok": True, "data": memory_service.summary_for(doc_id)}


@router.post("/documents/{doc_id}/memory/result")
def memory_result(doc_id: str, body: MemoryResult, session: Session = Depends(get_session)):
    if session.get(Document, doc_id) is None:
        raise HTTPException(404, "Document not found")
    return {"ok": True, "data": memory_service.record_document_result(doc_id, body.status == "stored", body.error, body.response)}


class StoredItems(BaseModel):
    items: list[dict] = Field(default_factory=list, max_length=2000)


@router.post("/cases/{case_id}/memory/items")
def stored_items(case_id: str, body: StoredItems, session: Session = Depends(get_session)):
    """n8n reports the case dataset's items ({id, name}) so answers can be traced to their source documents."""
    if session.get(Case, case_id) is None:
        raise HTTPException(404, "Case not found")
    return {"ok": True, "data": memory_service.record_items(case_id, body.items)}


@router.post("/cases/{case_id}/memory/graph-start")
def graph_start(case_id: str, session: Session = Depends(get_session)):
    if session.get(Case, case_id) is None:
        raise HTTPException(404, "Case not found")
    return {"ok": True, "data": memory_service.record_graph_start(case_id)}


@router.post("/cases/{case_id}/memory/graph-result")
def graph_result(case_id: str, body: GraphResult, session: Session = Depends(get_session)):
    if session.get(Case, case_id) is None:
        raise HTTPException(404, "Case not found")
    return {"ok": True, "data": memory_service.record_graph_result(case_id, body.status == "completed", body.detail)}
