"""Prepare the demo. Run from backend/ (or use seed.bat):

    python -m seed.seed_demo --reset                 fresh DB: 5 cases, Sharma Foods has no documents (live upload demo)
    python -m seed.seed_demo --reset --hero-docs     also process the 8 Sharma Foods documents (KAM view pre-filled)
    python -m seed.seed_demo --refresh-cache         live Sarvam + Cognee run; saves results to demo_cache/ (needs network)

--hero-docs uses demo_cache/ (no Sarvam calls) unless --live is given. The documents go through the real upload
endpoint and the real in-process pipeline (extract -> memory -> cross-check -> evidence boxes).
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
os.environ["PIPELINE_AUTORUN"] = "false"    # the seed drives the pipeline itself, synchronously

from app import config  # noqa: E402

HERO = "KYB-20814"
DOCS_DIR = BACKEND / "seed" / "sharma_foods"
HERO_QUESTIONS = [
    "Who owns more than 10% of Sharma Foods, directly or indirectly?",
    "Who is the authorised signatory and are they a director?",
    "What address does the GST certificate give for the principal place of business?",
    "What name is on the cancelled cheque?",
]


def reset() -> None:
    """Delete the local app DB and stored uploads. Touches only these two locations inside backend/."""
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(config.DB_PATH) + suffix)
        if p.exists():
            p.unlink()
    storage = config.STORAGE_DIR.resolve()
    if storage.exists() and storage.parent == BACKEND.resolve():
        for child in storage.iterdir():
            if child.is_dir() and child.name.startswith("KYB-"):
                shutil.rmtree(child)
    print(f"reset: removed {config.DB_PATH.name} and storage/KYB-*")


def ensure_docs() -> list[Path]:
    from seed.make_docs import HERO_FILES, generate
    if not all((DOCS_DIR / name).exists() for name in HERO_FILES):
        generate(DOCS_DIR)
    return [DOCS_DIR / name for name in HERO_FILES]


class _MemoryOff:
    """Stand-in store for --no-memory: every call reports Cognee as unavailable."""
    name = "off"

    def __getattr__(self, _name):
        from app.memory.base import MemoryUnavailable

        def unavailable(*_a, **_k):
            raise MemoryUnavailable("memory disabled for this seed run (--no-memory)")
        return unavailable


def load_hero_docs(live: bool, memory_on: bool) -> None:
    from fastapi.testclient import TestClient

    from app import memory, orchestrator
    from app.main import app

    config.DEMO_MODE = not live
    if not memory_on:
        memory.set_store(_MemoryOff())
    with TestClient(app) as client:
        files = [("files", (p.name, p.read_bytes(), "application/pdf")) for p in ensure_docs()]
        r = client.post(f"/api/cases/{HERO}/documents", files=files)
        r.raise_for_status()
        ids = r.json()["data"]["doc_ids"]
        print(f"uploaded {len(ids)} Sharma Foods documents; running the pipeline ({'live Sarvam' if live else 'cached Sarvam'})...")
        orchestrator.run_batch(HERO, ids)
        case = client.get(f"/api/cases/{HERO}").json()["data"]
        docs = client.get(f"/api/cases/{HERO}/documents").json()["data"]
        print(f"route {case['route']} | graph {case['graphStatus']}")
        for d in docs:
            boxes = sum(1 for f in (d["fields"] or {}).values() if f.get("box") or f.get("boxes"))
            print(f"  {d['filename']:34} {d['status']:10} memory {d['memory_status']:7} boxes {boxes}")


def warm_ask_cache() -> None:
    """Ask the standard demo questions live so DEMO_MODE (or a Cognee outage) can serve the saved answers."""
    from app import memory_service
    from app.memory import MemoryUnavailable

    config.DEMO_MODE = False
    for q in HERO_QUESTIONS:
        try:
            a = memory_service.ask(HERO, q)
            print(f"cached answer: {q}\n    -> {a['answer'][:110]}")
        except MemoryUnavailable as e:
            print(f"could not cache '{q}': {e}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows consoles default to cp1252
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reset", action="store_true", help="delete the local DB and uploads first")
    ap.add_argument("--hero-docs", action="store_true", help="process the 8 Sharma Foods documents")
    ap.add_argument("--live", action="store_true", help="with --hero-docs: call Sarvam live instead of demo_cache/")
    ap.add_argument("--no-memory", action="store_true", help="with --hero-docs: skip Cognee")
    ap.add_argument("--refresh-cache", action="store_true", help="reset + live run + save answers to the standard questions")
    args = ap.parse_args()

    if args.refresh_cache:
        args.reset, args.hero_docs, args.live = True, True, True
    if args.reset:
        reset()

    from sqlmodel import Session

    from app.db import engine, init_db
    from app.seed_cases import seed_if_empty

    init_db()
    with Session(engine) as s:
        n = seed_if_empty(s)
    print(f"seeded {n} cases" if n else "cases already present (use --reset for a clean start)")
    if args.hero_docs:
        load_hero_docs(live=args.live, memory_on=not args.no_memory)
    if args.refresh_cache:
        warm_ask_cache()


if __name__ == "__main__":
    main()
