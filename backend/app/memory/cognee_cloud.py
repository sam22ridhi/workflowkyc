"""Cognee Cloud over HTTP (verified against the tenant's /openapi.json, v1.6.2).

  POST /api/v1/add            multipart: data (file[]), datasetName         original file
  POST /api/v1/add_text       json: textData[], datasetName                 structured summary
  POST /api/v1/cognify        json: datasets[], runInBackground             -> pipeline_run_id (async server-side)
  GET  /api/v1/datasets/status?dataset=<uuid>                               -> {uuid: DATASET_PROCESSING_*}
  POST /api/v1/search         json: query, searchType, datasets[], includeReferences

Every call has a timeout. After repeated failures a short circuit-breaker fails fast, so one outage does not
make eight documents each wait out a full timeout.
"""
import re
import threading
import time

import httpx

from app import config
from app.memory.base import AddResult, CognifyResult, MemoryUnavailable, SearchResult

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
COGNIFY_WAIT_SECONDS = 300
STATUS_POLL_SECONDS = 4
BREAKER_FAILURES, BREAKER_COOLDOWN = 2, 20.0


class CogneeCloudStore:
    name = "cognee-cloud"

    def __init__(self):
        self._lock = threading.Lock()
        self._fails, self._open_until = 0, 0.0
        self._dataset_ids: dict[str, str] = {}

    # ---- plumbing ----
    def _client(self) -> httpx.Client:
        if not (config.COGNEE_BASE_URL and config.COGNEE_API_KEY):
            raise MemoryUnavailable("Cognee Cloud is not configured (COGNEE_BASE_URL / COGNEE_API_KEY).")
        return httpx.Client(
            base_url=config.COGNEE_BASE_URL, follow_redirects=True,
            headers={"X-Api-Key": config.COGNEE_API_KEY, "X-Tenant-Id": config.COGNEE_TENANT_ID},
            timeout=httpx.Timeout(config.COGNEE_TIMEOUT_SECONDS, connect=10.0),
        )

    def _request(self, method: str, path: str, **kw) -> httpx.Response:
        with self._lock:
            if time.monotonic() < self._open_until:
                raise MemoryUnavailable("Cognee Cloud is unavailable (recent failures); retrying shortly.")
        try:
            with self._client() as c:
                r = c.request(method, path, **kw)
        except MemoryUnavailable:
            raise
        except httpx.HTTPError as e:
            self._record(False)
            raise MemoryUnavailable(f"Cognee Cloud {type(e).__name__}: {str(e)[:150] or 'no response in time'}") from e
        if r.status_code in (401, 403):
            raise MemoryUnavailable(f"Cognee Cloud rejected the credentials ({r.status_code}). Check COGNEE_API_KEY / tenant.")
        if r.status_code >= 500:
            self._record(False)
        if r.status_code >= 400:
            raise MemoryUnavailable(f"Cognee Cloud {method} {path} -> {r.status_code}: {r.text[:200]}")
        self._record(True)
        return r

    def _record(self, ok: bool) -> None:
        with self._lock:
            self._fails = 0 if ok else self._fails + 1
            if self._fails >= BREAKER_FAILURES:
                self._open_until = time.monotonic() + BREAKER_COOLDOWN

    # ---- interface ----
    def add_document(self, dataset: str, *, file_path: str, filename: str, mime: str, summary_text: str) -> AddResult:
        ids: list[str] = []
        dataset_id = None
        with open(file_path, "rb") as fh:
            r = self._request("POST", "/api/v1/add", data={"datasetName": dataset}, files=[("data", (filename, fh, mime))])
        body = r.json()
        dataset_id = body.get("dataset_id")
        ids += [i["data_id"] for i in body.get("data_ingestion_info") or [] if i.get("data_id")]
        r = self._request("POST", "/api/v1/add_text", json={"textData": [summary_text], "datasetName": dataset})
        body = r.json()
        dataset_id = dataset_id or body.get("dataset_id")
        ids += [i["data_id"] for i in body.get("data_ingestion_info") or [] if i.get("data_id")]
        if dataset_id:
            self._dataset_ids[dataset] = dataset_id
        return AddResult(dataset_id=dataset_id, data_ids=ids)

    def cognify(self, dataset: str, dataset_id: str | None = None, wait: bool = True) -> CognifyResult:
        r = self._request("POST", "/api/v1/cognify", json={"datasets": [dataset], "runInBackground": True})
        run = next(iter(r.json().values()), {}) if isinstance(r.json(), dict) else {}
        dataset_id = dataset_id or run.get("dataset_id") or self._dataset_ids.get(dataset)
        if not wait or not dataset_id:
            return CognifyResult("started", run.get("pipeline_run_id"), "graph is building server-side")
        deadline = time.time() + COGNIFY_WAIT_SECONDS
        status = ""
        while time.time() < deadline:
            time.sleep(STATUS_POLL_SECONDS)
            body = self._request("GET", "/api/v1/datasets/status", params={"dataset": [dataset_id]}).json()
            status = str(body.get(dataset_id, ""))
            if "COMPLETED" in status:
                return CognifyResult("completed", run.get("pipeline_run_id"), status)
            if any(w in status for w in ("ERROR", "FAIL")):
                return CognifyResult("failed", run.get("pipeline_run_id"), status)
        raise MemoryUnavailable(f"Cognee graph build did not finish within {COGNIFY_WAIT_SECONDS}s (last status: {status or 'unknown'}).")

    def search(self, dataset: str, query: str, search_type: str = "GRAPH_COMPLETION", top_k: int = 15) -> SearchResult:
        r = self._request("POST", "/api/v1/search", json={"query": query, "searchType": search_type, "datasets": [dataset],
                                                         "topK": top_k, "includeReferences": True})
        body = r.json()
        parts: list[str] = []
        for item in body if isinstance(body, list) else [body]:
            res = item.get("search_result") if isinstance(item, dict) else item
            parts += [str(x) for x in (res if isinstance(res, list) else [res]) if x]
        text = "\n".join(parts).replace(" ", " ").strip()
        return SearchResult(answer=text, data_ids=list(dict.fromkeys(UUID_RE.findall(text))), raw=body)

    def health(self) -> dict:
        try:
            with self._client() as c:
                r = c.get("/health", timeout=10)
            return {"available": r.status_code == 200, "mode": "cloud", "detail": r.json().get("status")}
        except Exception as e:  # noqa: BLE001
            return {"available": False, "mode": "cloud", "detail": str(e)[:150]}
