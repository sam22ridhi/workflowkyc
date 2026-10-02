"""Triggers the document pipeline.

Primary path: POST {case_id, doc_ids} to the n8n webhook; n8n then calls our /extract, /memory, /cognify and
/cross-check endpoints. If n8n is unreachable we run the same steps in-process so an upload never stalls
(set N8N_FALLBACK_INPROCESS=false to disable).
"""
import logging

import httpx
from sqlmodel import Session

from app import config
from app.db import audit, engine
from app.models import Case

log = logging.getLogger("karyakarta.pipeline")


def run_in_process(case_id: str, doc_ids: list[str]) -> None:
    """Same sequence as the n8n workflow. Extraction/memory/cross-check steps are wired in later steps."""
    try:
        from app import orchestrator  # noqa: WPS433 (lazy: added in step 3+)
    except ImportError:
        with Session(engine) as s:
            audit(s, case_id, "agent", "Pipeline queued",
                  f"{len(doc_ids)} document(s) waiting for extraction.", "ai")
        return
    orchestrator.run_batch(case_id, doc_ids)


def trigger(case_id: str, doc_ids: list[str]) -> str:
    """Returns which path took the batch: 'n8n' | 'in_process' | 'none'. Never raises."""
    if not config.PIPELINE_AUTORUN:
        return "none"
    if config.N8N_WEBHOOK_URL:
        try:
            with Session(engine) as s:
                case = s.get(Case, case_id)
                dataset = f"case_{case.slug}" if case else None
            r = httpx.post(config.N8N_WEBHOOK_URL, json={"case_id": case_id, "doc_ids": doc_ids, "dataset": dataset}, timeout=5)
            r.raise_for_status()
            with Session(engine) as s:
                audit(s, case_id, "agent", "Workflow started", f"n8n accepted {len(doc_ids)} document(s).", "ai")
            return "n8n"
        except httpx.HTTPError as e:
            log.warning("n8n webhook failed (%s)", e)
            with Session(engine) as s:
                audit(s, case_id, "agent", "n8n unreachable",
                      "Falling back to the in-process pipeline." if config.N8N_FALLBACK_INPROCESS
                      else "Documents stay queued until n8n is back.", "warning")
    if config.N8N_WEBHOOK_URL and not config.N8N_FALLBACK_INPROCESS:
        return "none"
    run_in_process(case_id, doc_ids)
    return "in_process"
