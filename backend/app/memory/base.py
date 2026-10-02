"""The memory layer interface. Cognee (cloud or local) is behind this so the rest of the app never imports it.

Contract: methods raise MemoryUnavailable on any failure (timeout, bad key, outage). Callers record
`memory_status=failed` and carry on: memory never blocks extraction, checks or the UI.
"""
from dataclasses import dataclass, field
from typing import Protocol


class MemoryUnavailable(Exception):
    """Cognee could not be reached or refused the request."""


@dataclass
class AddResult:
    dataset_id: str | None
    data_ids: list[str] = field(default_factory=list)


@dataclass
class CognifyResult:
    status: str                      # completed | started | failed
    run_id: str | None = None
    detail: str = ""


@dataclass
class SearchResult:
    answer: str
    data_ids: list[str] = field(default_factory=list)   # Cognee data items the answer cites
    raw: object = None


class MemoryStore(Protocol):
    name: str

    def add_document(self, dataset: str, *, file_path: str, filename: str, mime: str, summary_text: str) -> AddResult: ...

    def cognify(self, dataset: str, dataset_id: str | None = None, wait: bool = True) -> CognifyResult: ...

    def search(self, dataset: str, query: str, search_type: str = "GRAPH_COMPLETION", top_k: int = 15) -> SearchResult: ...

    def health(self) -> dict: ...
