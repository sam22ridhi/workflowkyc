"""Cached Sarvam results, keyed by file SHA-256 + kind. Written after every successful live call.
With DEMO_MODE=true (or when the network fails) a cache hit is served instead, so the hero case works offline."""
import json
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_cache"


def _path(sha256: str, kind: str) -> Path:
    return CACHE_DIR / f"{sha256}.{kind}.json"


def get(sha256: str, kind: str) -> dict | None:
    p = _path(sha256, kind)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def put(sha256: str, kind: str, payload: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    _path(sha256, kind).write_text(json.dumps(payload, default=str), encoding="utf-8")
