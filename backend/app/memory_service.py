"""Memory orchestration: what we store in Cognee, when, and how failures are recorded.

Per document: the original file + a structured text summary (fields, confidences, pages, checks) go into the
case's dataset (case_<slug>). Once per batch the dataset is cognified into a knowledge graph. The KAM can then
ask questions. None of this decides pass/fail; rule checks stay in Python.
"""
import hashlib
import json
import logging
import re

from sqlmodel import Session, select

from app import config
from app.db import audit, engine
from app.doctypes import DOC_TYPES
from app.memory import MemoryUnavailable, get_store
from app.models import Case, Document, utcnow, VoiceCall
from app.sarvam import demo_cache
from app.sarvam.normalise import plain

log = logging.getLogger("karyakarta.memory")

_EVIDENCE_TAIL = re.compile(r"(\\n|\n)+\s*Evidence:.*$", re.S)


def dataset_name(case: Case) -> str:
    return f"case_{case.slug}"


def _fmt(value) -> str:
    if isinstance(value, list):
        return "; ".join(", ".join(f"{k}: {v}" for k, v in row.items() if v) if isinstance(row, dict) else str(row) for row in value)
    return str(value)


def document_summary(doc: Document, case: Case) -> str:
    """Plain-text description of one document, written for retrieval (names, numbers and relationships spelled out)."""
    label = DOC_TYPES.get(doc.doc_type, doc.doc_type)
    lines = [f"Document: {label}. Case {case.id}: {case.legal_name} ({case.entity_type.replace('_', ' ')}). "
             f"File {doc.filename}, SHA-256 {doc.sha256[:16]}."]
    for key, f in (doc.fields or {}).items():
        v = f.get("value") if isinstance(f, dict) else f
        if v in (None, "", []):
            continue
        page = f" (source page {f['page']})" if isinstance(f, dict) and f.get("page") else ""
        conf = f", confidence {f['confidence']:.0f}%" if isinstance(f, dict) and f.get("confidence") is not None else ""
        lines.append(f"{key.replace('_', ' ').capitalize()}: {_fmt(v)}{page}{conf}.")
    for c in doc.checks or []:
        lines.append(f"Check '{c['label']}': {c['status']} - {c['detail']}.")
    if doc.doc_type == "shareholding":
        lines.append("Beneficial ownership note: for a corporate shareholder, effective ownership of its partner equals "
                     "the corporate stake multiplied by the partner's stake in that entity.")
    return "\n".join(lines)


def store_document(doc_id: str) -> dict:
    """Add one document to the case dataset. Never raises: failure is recorded as memory_status='failed'."""
    with Session(engine) as s:
        doc = s.get(Document, doc_id)
        if doc is None:
            raise LookupError(doc_id)
        case = s.get(Case, doc.case_id)
        if not doc.fields:
            return _mark(s, doc, "failed", "Document has no extracted fields yet.", [])
        try:
            res = get_store().add_document(dataset_name(case), file_path=doc.path, filename=doc.filename,
                                           mime=doc.mime, summary_text=document_summary(doc, case))
        except (MemoryUnavailable, OSError) as e:
            return _mark(s, doc, "failed", str(e), [])
        except Exception as e:  # noqa: BLE001 - memory must never take the pipeline down
            log.exception("memory add failed for %s", doc_id)
            return _mark(s, doc, "failed", f"{type(e).__name__}: {e}", [])
        return _mark(s, doc, "stored", None, res.data_ids)


def _mark(s: Session, doc: Document, status: str, error: str | None, data_ids: list[str]) -> dict:
    doc.memory_status, doc.memory_error, doc.updated_at = status, (error or None) and error[:400], utcnow()
    if data_ids:
        doc.memory_data_ids = data_ids
    s.add(doc)
    s.commit()
    if status == "stored":
        audit(s, doc.case_id, "agent", "Stored in Cognee memory", f"{doc.filename} added to the case knowledge base.", "ai", doc.id)
    else:
        audit(s, doc.case_id, "agent", "Memory unavailable", f"{doc.filename}: {error}. Extraction and checks are unaffected.", "warning", doc.id)
    return {"doc_id": doc.id, "memory_status": status, "error": doc.memory_error}


def cognify_case(case_id: str) -> dict:
    """Build the knowledge graph for the case dataset. Never raises."""
    with Session(engine) as s:
        case = s.get(Case, case_id)
        if case is None:
            raise LookupError(case_id)
        stored = [d for d in s.query(Document).filter(Document.case_id == case_id) if d.memory_status == "stored"]
        if not stored:
            return _graph(s, case, "none", "No document is stored in memory yet; nothing to build.")
        case.graph_status = "building"
        s.add(case)
        s.commit()
        audit(s, case_id, "agent", "Building knowledge graph", f"Cognee is analysing {len(stored)} document(s).", "ai")
        try:
            res = get_store().cognify(dataset_name(case))
        except MemoryUnavailable as e:
            return _graph(s, case, "failed", str(e))
        except Exception as e:  # noqa: BLE001
            log.exception("cognify failed for %s", case_id)
            return _graph(s, case, "failed", f"{type(e).__name__}: {e}")
        return _graph(s, case, "ready" if res.status == "completed" else "failed" if res.status == "failed" else "building", res.detail)


def _graph(s: Session, case: Case, status: str, detail: str) -> dict:
    case.graph_status, case.graph_detail = status, detail[:400]
    s.add(case)
    s.commit()
    if status == "ready":
        audit(s, case.id, "agent", "Knowledge graph ready", "Ownership and entity relationships are searchable.", "success")
    elif status == "failed":
        audit(s, case.id, "agent", "Knowledge graph unavailable", f"{detail[:200]}. Case Q&A is offline; everything else works.", "warning")
    return {"case_id": case.id, "graph_status": status, "detail": detail}


def store_and_cognify(case_id: str, doc_ids: list[str]) -> None:
    """In-process equivalent of n8n's 'Cognee: store document' x N then 'Cognee: build knowledge graph'."""
    for doc_id in doc_ids:
        try:
            store_document(doc_id)
        except Exception:  # noqa: BLE001
            continue
    cognify_case(case_id)


def _cache_key(case_slug: str, question: str) -> str:
    return hashlib.sha256(f"{case_slug}|{question.strip().lower()}".encode()).hexdigest()


def ask(case_id: str, question: str) -> dict:
    """KAM Q&A over the case graph. Raises MemoryUnavailable (-> HTTP 503) when no live or cached answer exists."""
    with Session(engine) as s:
        case = s.get(Case, case_id)
        if case is None:
            raise LookupError(case_id)
        key = _cache_key(case.slug, question)
        cached = demo_cache.get(key, "ask")
        if config.DEMO_MODE and cached:
            return {**cached, "from_cache": True}
        try:
            res = get_store().search(dataset_name(case), question)
        except MemoryUnavailable as e:
            if cached:
                return {**cached, "from_cache": True, "note": f"Cognee unavailable ({e}); showing the last saved answer."}
            raise
        answer = _EVIDENCE_TAIL.sub("", res.answer).strip()
        ids = set(res.data_ids)
        docs = [d for d in s.query(Document).filter(Document.case_id == case_id) if ids & set(d.memory_data_ids or [])]
        out = {"question": question, "answer": answer or "No answer found in this case's documents.",
               "sources": [{"doc_id": d.id, "filename": d.filename, "doc_type": d.doc_type,
                            "doc_type_label": DOC_TYPES.get(d.doc_type, d.doc_type)} for d in docs],
               "from_cache": False}
        if answer:
            demo_cache.put(key, "ask", out)
        audit(s, case_id, "kam", "Asked the case memory", question[:200], "ai")
        return out


# ---------------------------------------------------------------- n8n-native Cognee nodes report back here
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def summary_for(doc_id: str) -> dict:
    """What n8n's 'Cognee: store document' node should store for this document."""
    with Session(engine) as s:
        doc = s.get(Document, doc_id)
        if doc is None:
            raise LookupError(doc_id)
        case = s.get(Case, doc.case_id)
        # Cognee Cloud refuses a second upload with the same file name and different content, so every item
        # gets its own file name prefix (the node adds "-1"; Cognee lists the item as "<prefix>-1").
        return {"doc_id": doc.id, "case_id": case.id, "dataset": dataset_name(case), "ready": bool(doc.fields),
                "file_prefix": f"doc-{doc.id}", "text": document_summary(doc, case) if doc.fields else ""}


def record_items(case_id: str, items: list[dict]) -> dict:
    """n8n listed the case dataset's stored items; remember each document's Cognee data id (used to name answer sources)."""
    by_name = {str(i.get("name", "")): str(i.get("id", "")) for i in items if i.get("id")}
    linked = 0
    with Session(engine) as s:
        for doc in s.exec(select(Document).where(Document.case_id == case_id)):
            data_id = by_name.get(f"doc-{doc.id}-1") or by_name.get(f"doc-{doc.id}")
            if data_id and _UUID.fullmatch(data_id):
                doc.memory_data_ids = [data_id]
                s.add(doc)
                linked += 1
        s.commit()
    return {"case_id": case_id, "linked_documents": linked, "items_seen": len(items)}


def record_document_result(doc_id: str, ok: bool, error: str | None, response) -> dict:
    """n8n stored (or failed to store) a document with the native Cognee node. Collect Cognee data_ids from
    its response (data_ingestion_info[].data_id) so /ask can map answers back to documents."""
    with Session(engine) as s:
        doc = s.get(Document, doc_id)
        if doc is None:
            raise LookupError(doc_id)
        ids: list[str] = []

        def walk(node):
            if isinstance(node, dict):
                if isinstance(node.get("data_id"), str):
                    ids.append(node["data_id"])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(response)
        if ok:
            return _mark(s, doc, "stored", None, list(dict.fromkeys(i for i in ids if _UUID.fullmatch(i))))
        return _mark(s, doc, "failed", error or "Cognee node reported an error.", [])


def record_graph_start(case_id: str) -> dict:
    with Session(engine) as s:
        case = s.get(Case, case_id)
        if case is None:
            raise LookupError(case_id)
        case.graph_status = "building"
        s.add(case)
        s.commit()
        audit(s, case_id, "agent", "Building knowledge graph", "n8n started Cognee cognify for this case.", "ai")
        return {"case_id": case_id, "graph_status": "building"}


def record_graph_result(case_id: str, ok: bool, detail: str | None) -> dict:
    with Session(engine) as s:
        case = s.get(Case, case_id)
        if case is None:
            raise LookupError(case_id)
        stored = (s.query(Document).filter(Document.case_id == case_id, Document.memory_status == "stored").count()
                  + s.query(VoiceCall).filter(VoiceCall.case_id == case_id, VoiceCall.memory_status == "stored").count())
        if ok and not stored:   # Cognee "completes" a cognify of an empty dataset; nothing stored (documents or call records) means nothing to search
            return _graph(s, case, "none", "No document of this case is stored in memory yet, so there is no graph to search.")
        return _graph(s, case, "ready" if ok else "failed", detail or ("cognify completed" if ok else "cognify failed"))
