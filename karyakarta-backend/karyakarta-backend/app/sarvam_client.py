"""Thin wrapper around Sarvam Document Intelligence (schema-based Extract).

Flow (async job on Sarvam's side):
  1. client.doc_ai.extract(file=..., schema=...)  -> job_id
  2. poll client.doc_ai.get_status(job_id)        -> until terminal state
  3. client.doc_ai.get_results(job_id)            -> {"result": {...}, "annotations": {...}}
"""
import json
import mimetypes
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()

TERMINAL = {"completed", "partially_completed", "failed", "rejected"}
OK = {"completed", "partially_completed"}
POLL_SECONDS = 6       # Sarvam's documented rate limit is 10 requests/minute; don't poll faster
TIMEOUT_SECONDS = 180

_client = None


def client() -> SarvamAI:
    global _client
    if _client is None:
        key = os.environ.get("SARVAM_API_KEY")
        if not key:
            raise RuntimeError("SARVAM_API_KEY is not set (put it in .env)")
        _client = SarvamAI(api_subscription_key=key)
    return _client


def _to_dict(obj):
    """SDK responses are pydantic models; turn them into plain dicts/lists."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return obj


def extract(path: str, schema: dict, language: str = "en-IN") -> dict:
    """Run a schema-based extraction on one file and return the raw Sarvam results as a dict."""
    p = Path(path)
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    c = client()

    with open(p, "rb") as f:
        job = c.doc_ai.extract(
            file=[(p.name, f, mime)],
            schema=json.dumps(schema),
            language=language,
            output_format="json",
        )

    started = time.time()
    while True:
        status = c.doc_ai.get_status(job_id=job.job_id).status.lower()
        if status in TERMINAL:
            break
        if time.time() - started > TIMEOUT_SECONDS:
            raise TimeoutError(f"Sarvam job {job.job_id} still '{status}' after {TIMEOUT_SECONDS}s")
        time.sleep(POLL_SECONDS)

    if status not in OK:
        raise RuntimeError(f"Sarvam job {job.job_id} ended with status '{status}'")

    results = _to_dict(c.doc_ai.get_results(job_id=job.job_id))
    return {"job_id": job.job_id, "status": status, "raw": results,
            "seconds": round(time.time() - started, 1)}
