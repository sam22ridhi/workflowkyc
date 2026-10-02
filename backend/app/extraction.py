"""Extraction service: Sarvam extract + digitise -> normalised fields, boxes, per-document checks.

  extract_document(doc_id)  fields + confidence + page + checks (fast path; what n8n waits for)
  locate_document(doc_id)   evidence boxes from Sarvam digitise (slower, runs after fields are visible)

Both write audit events, so the KAM screen updates live over SSE. Cached results (demo_cache/) are served when
DEMO_MODE=true, or when the live call fails and a cached result for the same file exists.
"""
import logging
import time

from sqlmodel import Session

from app import config
from app.checks.validators import check_document, summarise
from app.db import audit, engine
from app.doctypes import DOC_TYPES
from app.models import Case, Document, utcnow
from app.sarvam import client as sarvam
from app.sarvam import demo_cache
from app.sarvam.normalise import classify_text, digitise_text, locate_boxes, plain, to_fields
from app.sarvam.schemas import SCHEMAS

log = logging.getLogger("karyakarta.extraction")


class ExtractionError(Exception):
    pass


def _call(kind: str, sha: str, live, note) -> dict:
    """Run a Sarvam call with cache fallback. Returns {raw, seconds, job_id, cached}."""
    cached = demo_cache.get(sha, kind)
    if config.DEMO_MODE and cached:
        return {"raw": cached, "seconds": 0.0, "job_id": cached.get("job_id"), "cached": True}
    try:
        out = live()
    except Exception as e:  # noqa: BLE001
        if cached:
            note(f"Sarvam unavailable ({e}); served cached result.")
            return {"raw": cached, "seconds": 0.0, "job_id": cached.get("job_id"), "cached": True}
        raise
    demo_cache.put(sha, kind, out["raw"])
    return {**out, "cached": False}


def describe_error(e: Exception) -> str:
    """Short, human-readable error. Sarvam SDK errors carry status_code + body; their str() dumps HTTP headers."""
    code, body = getattr(e, "status_code", None), getattr(e, "body", None)
    if code is None:
        return f"{type(e).__name__}: {e}"[:300]
    detail = None
    if isinstance(body, dict):
        err = body.get("error")
        detail = (body.get("detail") or body.get("title") or body.get("message")
                  or (err.get("message") if isinstance(err, dict) else err))
    detail = detail or (body if isinstance(body, str) else None) or type(e).__name__
    return f"Sarvam rejected the file (HTTP {code}): {str(detail)[:240]}"


def _fail(session: Session, doc: Document, message: str) -> None:
    doc.status, doc.error, doc.updated_at = "error", message[:500], utcnow()
    session.add(doc)
    session.commit()
    audit(session, doc.case_id, "agent", "Extraction failed", f"{doc.filename}: {message[:200]}", "warning", doc.id)


def extract_document(doc_id: str) -> dict:
    with Session(engine) as s:
        doc = s.get(Document, doc_id)
        if doc is None:
            raise LookupError(doc_id)
        case = s.get(Case, doc.case_id)
        started = time.time()
        doc.status, doc.error, doc.updated_at = "extracting", None, utcnow()
        s.add(doc)
        s.commit()
        audit(s, doc.case_id, "agent", "Extraction started", f"{doc.filename} · {DOC_TYPES.get(doc.doc_type)}", "ai", doc.id)
        note = lambda msg: audit(s, doc.case_id, "agent", "Using cached result", f"{doc.filename}: {msg}", "warning", doc.id)  # noqa: E731

        try:
            raw_store = dict(doc.raw or {})
            if doc.doc_type not in SCHEMAS:  # unknown: OCR first, classify by keywords, then extract
                dg = _call("digitise", doc.sha256, lambda: sarvam.digitise(doc.path), note)
                raw_store["digitise"] = dg["raw"]
                guessed, hits = classify_text(digitise_text(dg["raw"]))
                if guessed == "unknown":
                    doc.raw, doc.status = raw_store, "needs_attention"
                    doc.error = "Could not identify the document type; please set it manually."
                    s.add(doc)
                    s.commit()
                    audit(s, doc.case_id, "agent", "Document type unknown", f"{doc.filename}: KAM to set the type.", "warning", doc.id)
                    return _result(doc, {}, [], 0.0)
                doc.doc_type = guessed
                audit(s, doc.case_id, "agent", "Document classified", f"{doc.filename} → {DOC_TYPES[guessed]} ({hits} keyword hits)", "ai", doc.id)

            schema = SCHEMAS[doc.doc_type]
            ex = _call(f"extract-{doc.doc_type}", doc.sha256, lambda: sarvam.extract(doc.path, schema), note)
            raw_store["extract"] = ex["raw"]
            fields = to_fields(ex["raw"], schema)
            if "digitise" in raw_store:   # classification already paid for the layout pass: boxes are free
                locate_boxes(fields, raw_store["digitise"])
            checks = check_document(doc.doc_type, plain(fields), case)
            doc.fields, doc.checks, doc.raw = fields, checks, raw_store
            doc.page_count = (ex["raw"].get("usage") or {}).get("pages_total")
            doc.sarvam_job_id = ex.get("job_id") or ex["raw"].get("job_id")
            doc.status = "needs_attention" if summarise(checks) == "needs_attention" else "extracted"
            doc.updated_at = utcnow()
            s.add(doc)
            s.commit()
        except Exception as e:  # noqa: BLE001 - surface to n8n and the UI, never crash the worker
            log.exception("extraction failed for %s", doc_id)
            message = describe_error(e)
            _fail(s, doc, message)
            raise ExtractionError(message) from e

        n = sum(1 for v in fields.values() if v.get("value") not in (None, "", []))
        confs = [v["confidence"] for v in fields.values() if v.get("confidence") is not None]
        avg = f"{sum(confs) / len(confs):.0f}%" if confs else "n/a"
        failed = [c["label"] for c in checks if c["status"] == "fail"]
        audit(s, doc.case_id, "agent", f"{DOC_TYPES[doc.doc_type]} extracted",
              f"{n}/{len(fields)} fields · avg confidence {avg} · {time.time() - started:.0f}s"
              + (f" · failed checks: {', '.join(failed)}" if failed else ""),
              "warning" if failed else "success", doc.id)
        return _result(doc, fields, checks, ex["seconds"])


def _result(doc: Document, fields: dict, checks: list, seconds: float) -> dict:
    return {"doc_id": doc.id, "status": doc.status, "checks_passed": not any(c["status"] == "fail" for c in checks),
            "boxes": "ready" if any(v.get("box") or v.get("boxes") for v in fields.values()) else "pending",
            "seconds": seconds}


def locate_document(doc_id: str) -> str:
    """Adds evidence boxes. Returns 'ready' | 'unavailable' | 'skipped'. Never raises (boxes are a nicety)."""
    with Session(engine) as s:
        doc = s.get(Document, doc_id)
        if doc is None or not doc.fields:
            return "skipped"
        if any(v.get("box") or v.get("boxes") for v in doc.fields.values()):
            return "ready"
        try:
            note = lambda msg: audit(s, doc.case_id, "agent", "Using cached result", f"{doc.filename}: {msg}", "warning", doc.id)  # noqa: E731
            dg = _call("digitise", doc.sha256, lambda: sarvam.digitise(doc.path), note)
            fields = locate_boxes({k: dict(v) for k, v in doc.fields.items()}, dg["raw"])
            doc.fields, doc.raw = fields, {**(doc.raw or {}), "digitise": dg["raw"]}
            doc.updated_at = utcnow()
            s.add(doc)
            s.commit()
            located = sum(1 for v in fields.values() if v.get("box") or v.get("boxes"))
            audit(s, doc.case_id, "agent", "Evidence highlights ready",
                  f"{doc.filename}: {located}/{len(fields)} fields located on the page", "ai", doc.id)
            return "ready"
        except Exception as e:  # noqa: BLE001
            log.warning("locate failed for %s: %s", doc_id, e)
            audit(s, doc.case_id, "agent", "Evidence highlights unavailable", f"{doc.filename}: {str(e)[:150]}", "warning", doc.id)
            return "unavailable"
