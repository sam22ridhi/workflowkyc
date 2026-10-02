from app import config
from app.memory.base import MemoryStore, MemoryUnavailable

_store: MemoryStore | None = None


def get_store() -> MemoryStore:
    """COGNEE_MODE=cloud|local picks the implementation. Local imports the heavy `cognee` library lazily."""
    global _store
    if _store is None:
        if config.COGNEE_MODE == "local":
            from app.memory.cognee_local import CogneeLocalStore
            _store = CogneeLocalStore()
        else:
            from app.memory.cognee_cloud import CogneeCloudStore
            _store = CogneeCloudStore()
    return _store


def set_store(store: MemoryStore | None) -> None:
    """Tests inject a fake here."""
    global _store
    _store = store


__all__ = ["MemoryStore", "MemoryUnavailable", "get_store", "set_store"]
