"""Sarvam Document Intelligence client.

Two async-job pipelines on Sarvam's side, both: submit -> poll status -> fetch results.
  extract   : schema-based field extraction; results carry values + confidence + page (no coordinates)
  digitise  : full-page layout JSON; blocks carry text + bbox_norm (0-1) + pixel coordinates

Rate limit (measured, see README): Sarvam allows 10 requests/minute for job *submission*; status and result
calls were not throttled. So a process-wide sliding window guards submissions, and in-flight jobs are capped.
"""
import json
import logging
import mimetypes
import os
import threading
import time
from collections import deque
from pathlib import Path

from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()
log = logging.getLogger("karyakarta.sarvam")

TERMINAL = {"completed", "partially_completed", "failed", "rejected"}
OK = {"completed", "partially_completed"}
POLL_SECONDS = 2.0
TIMEOUT_SECONDS = 180
SUBMITS_PER_MINUTE = int(os.environ.get("SARVAM_SUBMITS_PER_MINUTE", "9"))   # limit is 10; keep one spare
MAX_IN_FLIGHT = int(os.environ.get("SARVAM_MAX_IN_FLIGHT", "3"))
MAX_ATTEMPTS = 3


class SubmitLimiter:
    """Sliding-window limiter: at most `n` acquisitions in any 60 s window (thread-safe)."""

    def __init__(self, n: int, window: float = 60.0):
        self.n, self.window = n, window
        self._stamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """Blocks until a slot is free. Returns seconds waited."""
        waited = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                while self._stamps and now - self._stamps[0] >= self.window:
                    self._stamps.popleft()
                if len(self._stamps) < self.n:
                    self._stamps.append(now)
                    return waited
                sleep_for = self.window - (now - self._stamps[0]) + 0.05
            time.sleep(sleep_for)
            waited += sleep_for


limiter = SubmitLimiter(SUBMITS_PER_MINUTE)
in_flight = threading.BoundedSemaphore(MAX_IN_FLIGHT)
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


def _retryable(e: Exception) -> bool:
    code = getattr(e, "status_code", None)
    if code is not None:
        return code == 429 or code >= 500
    return isinstance(e, (ConnectionError, TimeoutError, OSError)) or "timeout" in type(e).__name__.lower()


def _with_retries(fn, what: str):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            if attempt == MAX_ATTEMPTS or not _retryable(e):
                raise
            delay = 2 ** attempt
            log.warning("Sarvam %s failed (%s); retry %d in %ds", what, e, attempt, delay)
            time.sleep(delay)


def _run_job(submit, label: str) -> dict:
    """Common flow: acquire a submit slot, submit, poll, fetch. Returns {job_id, status, raw, seconds}."""
    c = client()
    with in_flight:
        limiter.acquire()
        started = time.time()
        job = _with_retries(submit, f"{label} submit")
        while True:
            status = _with_retries(lambda: c.doc_ai.get_status(job_id=job.job_id), f"{label} status").status.lower()
            if status in TERMINAL:
                break
            if time.time() - started > TIMEOUT_SECONDS:
                raise TimeoutError(f"Sarvam {label} job {job.job_id} still '{status}' after {TIMEOUT_SECONDS}s")
            time.sleep(POLL_SECONDS)
        if status not in OK:
            raise RuntimeError(f"Sarvam {label} job {job.job_id} ended with status '{status}'")
        raw = _to_dict(_with_retries(lambda: c.doc_ai.get_results(job_id=job.job_id), f"{label} results"))
        return {"job_id": job.job_id, "status": status, "raw": raw, "seconds": round(time.time() - started, 1)}


def extract(path: str, schema: dict, language: str = "en-IN") -> dict:
    p = Path(path)
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"

    def submit():
        with open(p, "rb") as f:
            return client().doc_ai.extract(file=[(p.name, f, mime)], schema=json.dumps(schema),
                                           language=language, output_format="json")

    return _run_job(submit, "extract")


def digitise(path: str, language: str = "en-IN") -> dict:
    p = Path(path)
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"

    def submit():
        with open(p, "rb") as f:
            return client().doc_ai.digitise(file=[(p.name, f, mime)], language=language, output_format="json")

    return _run_job(submit, "digitise")
