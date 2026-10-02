"""In-process version of the n8n workflow (used when n8n is unreachable). Same order of steps:
extract each document -> (memory + cross-check wired in steps 5/6) -> evidence boxes."""
import logging

from sqlmodel import Session

from app import extraction
from app.db import audit, engine

log = logging.getLogger("karyakarta.orchestrator")


def run_batch(case_id: str, doc_ids: list[str]) -> None:
    ok = 0
    for doc_id in doc_ids:
        try:
            extraction.extract_document(doc_id)
            ok += 1
        except Exception:  # noqa: BLE001 - already audited per document
            continue
    try:
        from app import memory_service  # step 5
        memory_service.store_and_cognify(case_id, doc_ids)
    except ImportError:
        pass
    try:
        from app.checks import cross_check  # step 6
        cross_check.run(case_id)
    except ImportError:
        with Session(engine) as s:
            audit(s, case_id, "agent", "Extraction complete", f"{ok}/{len(doc_ids)} document(s) extracted.", "ai")
    for doc_id in doc_ids:   # boxes last: fields are already visible to the KAM
        extraction.locate_document(doc_id)
