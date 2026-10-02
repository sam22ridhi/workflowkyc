"""Cognee running locally (the `cognee` Python library with its defaults: SQLite + LanceDB + Kuzu).

The demo-day fallback if the cloud tenant is down: COGNEE_MODE=local. Install separately (heavy dependency tree):
    pip install -r requirements-local.txt
`cognify` needs an LLM for entity extraction. Cognee reads it from the environment (LLM_API_KEY, optionally
LLM_PROVIDER / LLM_MODEL); add / search of raw chunks work without one. Without a key cognify raises, which the
memory service records as graph_status='failed' and everything else keeps working.
"""
import asyncio
import os
import threading

from app import config
from app.memory.base import AddResult, CognifyResult, MemoryUnavailable, SearchResult


class CogneeLocalStore:
    name = "cognee-local"

    def __init__(self):
        # Keep local data inside the project (gitignored) rather than inside site-packages.
        root = str(config.BASE_DIR / "cognee_data")
        os.environ.setdefault("DATA_ROOT_DIRECTORY", os.path.join(root, "data"))
        os.environ.setdefault("SYSTEM_ROOT_DIRECTORY", os.path.join(root, "system"))
        self._lock = threading.Lock()   # the local SQLite/Kuzu stores are single-writer

    @staticmethod
    def _import():
        try:
            import cognee  # noqa: WPS433
            from cognee import SearchType
            return cognee, SearchType
        except ImportError as e:
            raise MemoryUnavailable("Local Cognee is not installed (pip install -r requirements-local.txt).") from e

    @staticmethod
    def _run(coro, timeout: float):
        try:
            return asyncio.run(asyncio.wait_for(coro, timeout))
        except asyncio.TimeoutError as e:
            raise MemoryUnavailable(f"Local Cognee timed out after {timeout:.0f}s.") from e
        except MemoryUnavailable:
            raise
        except Exception as e:  # noqa: BLE001
            raise MemoryUnavailable(f"Local Cognee {type(e).__name__}: {str(e)[:200]}") from e

    def add_document(self, dataset: str, *, file_path: str, filename: str, mime: str, summary_text: str) -> AddResult:
        cognee, _ = self._import()

        async def go():
            await cognee.add(file_path, dataset_name=dataset)
            await cognee.add(summary_text, dataset_name=dataset)

        with self._lock:
            self._run(go(), 300)
        return AddResult(dataset_id=dataset)

    def cognify(self, dataset: str, dataset_id: str | None = None, wait: bool = True) -> CognifyResult:
        cognee, _ = self._import()
        with self._lock:
            self._run(cognee.cognify(datasets=[dataset]), 600)
        return CognifyResult("completed", None, "local graph built")

    def search(self, dataset: str, query: str, search_type: str = "GRAPH_COMPLETION", top_k: int = 15) -> SearchResult:
        cognee, SearchType = self._import()
        with self._lock:
            hits = self._run(cognee.search(query_text=query, query_type=getattr(SearchType, search_type),
                                           datasets=[dataset], top_k=top_k), 120)
        text = "\n".join(str(h) for h in (hits if isinstance(hits, list) else [hits]) if h)
        return SearchResult(answer=text.strip(), data_ids=[], raw=hits)

    def health(self) -> dict:
        try:
            self._import()
            return {"available": True, "mode": "local", "detail": "cognee library importable"}
        except MemoryUnavailable as e:
            return {"available": False, "mode": "local", "detail": str(e)}
