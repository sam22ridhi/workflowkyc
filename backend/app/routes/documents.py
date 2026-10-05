from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from typing import Literal

from app import case_admin, extraction
from app.db import audit, get_session
from app.doctypes import DOC_TYPES
from app.models import Document, utcnow
from app.schemas_api import DocTypeUpdate, DocumentOut, Envelope, ExtractOut, StatusUpdate
from app.serializers import doc_out

router = APIRouter(prefix="/api")


def get_doc(session: Session, doc_id: str) -> Document:
    doc = session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("/documents/{doc_id}", response_model=Envelope[DocumentOut])
def read_document(doc_id: str, session: Session = Depends(get_session)):
    return Envelope(data=doc_out(get_doc(session, doc_id)))


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, actor: Literal["merchant", "kam", "compliance", "agent"] = "kam", session: Session = Depends(get_session)):
    """KAM only, before the case is submitted to Compliance: removes the file, re-runs the checks on what is left, forgets it in the merchant twin."""
    return {"ok": True, "data": case_admin.delete_document(session, get_doc(session, doc_id), actor)}


@router.get("/documents/{doc_id}/file")
def document_file(doc_id: str, session: Session = Depends(get_session)):
    """Streams the original upload for the in-browser viewer (inline, correct content-type)."""
    doc = get_doc(session, doc_id)
    path = Path(doc.path)
    if not path.exists():
        raise HTTPException(410, "Stored file is missing on disk")
    return FileResponse(path, media_type=doc.mime, filename=doc.filename, content_disposition_type="inline")


@router.post("/documents/{doc_id}/status", response_model=Envelope[DocumentOut])
def set_status(doc_id: str, body: StatusUpdate, session: Session = Depends(get_session)):
    """Used by n8n's error branches to mark a document failed (and by anything else that moves a status)."""
    doc = get_doc(session, doc_id)
    doc.status = body.status
    message = (body.message or "")[:500] or None
    doc.error = (message or doc.error) if body.status == "error" else None
    doc.updated_at = utcnow()
    session.add(doc)
    session.commit()
    audit(session, doc.case_id, "agent", f"Document {body.status}",
          f"{doc.filename}: {(message or body.status)[:200]}", "warning" if body.status == "error" else "ai", doc.id)
    session.refresh(doc)
    return Envelope(data=doc_out(doc))


@router.post("/documents/{doc_id}/type", response_model=Envelope[DocumentOut])
def set_type(doc_id: str, body: DocTypeUpdate, session: Session = Depends(get_session)):
    """KAM corrects a mis-detected document type; the document goes back to 'received' for re-extraction."""
    if body.doc_type not in DOC_TYPES:
        raise HTTPException(400, f"Unknown doc_type. Known: {list(DOC_TYPES)}")
    doc = get_doc(session, doc_id)
    old, doc.doc_type, doc.status, doc.updated_at = doc.doc_type, body.doc_type, "received", utcnow()
    session.add(doc)
    session.commit()
    audit(session, doc.case_id, "kam", "Document type corrected", f"{doc.filename}: {old} → {body.doc_type}",
          "neutral", doc.id)
    session.refresh(doc)
    return Envelope(data=doc_out(doc))


@router.post("/documents/{doc_id}/extract", response_model=Envelope[ExtractOut])
def extract(doc_id: str, background: BackgroundTasks, session: Session = Depends(get_session)):
    """n8n calls this per document. Blocks until fields are extracted (a plain `def`, so it runs in a worker
    thread); evidence boxes are located afterwards in the background so the KAM sees fields first."""
    get_doc(session, doc_id)
    try:
        result = extraction.extract_document(doc_id)
    except extraction.ExtractionError as e:
        raise HTTPException(502, f"Extraction failed: {e}")
    background.add_task(extraction.locate_document, doc_id)
    session.expire_all()
    return Envelope(data=ExtractOut(**result, document=doc_out(session.get(Document, doc_id))))


@router.post("/documents/{doc_id}/locate", response_model=Envelope[DocumentOut])
def locate(doc_id: str, session: Session = Depends(get_session)):
    """(Re)compute evidence boxes for an already-extracted document."""
    get_doc(session, doc_id)
    extraction.locate_document(doc_id)
    session.expire_all()
    return Envelope(data=doc_out(session.get(Document, doc_id)))
