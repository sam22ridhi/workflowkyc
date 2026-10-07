"""Record a read-only snapshot of the Sharma Foods case so the frontend can show it WITHOUT a backend (a frontend-only deployment).

    python scripts/export_static_snapshot.py            (from backend/; uses a throw-away database, never your real one)

What it does, on a temporary database:
  1. puts Sharma Foods (KYB-20814) at its starting state and uploads the realistic demo pack (seed/demo_pack) through the real pipeline
     (recorded Sarvam results from demo_cache/, so no Sarvam credit is needed; Cognee is used live for the knowledge graph);
  2. asks the three suggested "Ask this case" questions (plus two more) and records Cognee's answers and sources;
  3. records the case list, every case's detail, the documents with their evidence boxes, the filled MAF form, the Annapurna settlement view,
     and copies the PDFs;
  4. writes ../public/demo/snapshot.json and ../public/demo/files/*.pdf, then resets the case (which also deletes its Cognee dataset).
Everything in the snapshot is real output of the system on the synthetic pack. It takes about 4 minutes.
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

tmp = Path(tempfile.mkdtemp(prefix="karyakarta_snapshot_"))
os.environ["KARYAKARTA_DB"] = str(tmp / "snapshot.db")
os.environ["KARYAKARTA_STORAGE"] = str(tmp / "storage")
os.environ["PIPELINE_AUTORUN"] = "false"
os.environ["FINOPS_SEED_DEMO"] = "true"
os.environ["N8N_WEBHOOK_URL"] = ""
os.environ["CPV_ALLOW_DEMO_REFERENCE"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app import config, orchestrator  # noqa: E402
from app.main import app  # noqa: E402
from seed.seed_demo import ensure_docs  # noqa: E402

HERO = "KYB-20814"
SETTLEMENT = "KYB-20820"
OUT = BACKEND.parent / "public" / "demo"
QUESTIONS = [
    "Who owns more than 10% of this company, directly or indirectly?",
    "Who is the authorised signatory and are they a director?",
    "Which address does each document give?",
    "What name, account number and IFSC are on the cancelled cheque?",
    "Which documents has the merchant uploaded?",
]


def norm(q: str) -> str:
    return " ".join(q.lower().split()).rstrip("?. ")


def main() -> None:
    config.DEMO_MODE = True              # recorded Sarvam results; Cognee stays live
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "files").mkdir(exist_ok=True)
    for old in (OUT / "files").glob("*.pdf"):
        old.unlink()

    with TestClient(app) as client:
        r = client.post(f"/api/cases/{HERO}/demo/reset")
        r.raise_for_status()
        files = [("files", (p.name, p.read_bytes(), "application/pdf")) for p in ensure_docs("realistic")]
        ids = client.post(f"/api/cases/{HERO}/documents", files=files).json()["data"]["doc_ids"]
        print(f"uploaded {len(ids)} documents; running the pipeline (about 3 minutes)...")
        orchestrator.run_batch(HERO, ids)
        config.DEMO_MODE = False             # from here on Cognee is asked live: a saved answer from an earlier run would cite documents that are not in this snapshot

        listing = client.get("/api/cases").json()["data"]
        details = {row["id"]: client.get(f"/api/cases/{row['id']}").json()["data"] for row in listing["items"]}
        documents = {HERO: client.get(f"/api/cases/{HERO}/documents").json()["data"]}
        crm = {HERO: client.get(f"/api/cases/{HERO}/crm-form").json()["data"]}
        settlements = {SETTLEMENT: client.get(f"/api/cases/{SETTLEMENT}/settlements").json()["data"]} if SETTLEMENT in details else {}

        for d in documents[HERO]:
            blob = client.get(f"/api/documents/{d['doc_id']}/file")
            blob.raise_for_status()
            (OUT / "files" / f"{d['doc_id']}.pdf").write_bytes(blob.content)

        asks: dict[str, dict] = {HERO: {}}
        for q in QUESTIONS:
            res = client.post(f"/api/cases/{HERO}/ask", json={"question": q})
            if res.status_code == 200:
                data = res.json()["data"]
                assert not data.get("from_cache"), "a saved answer was served; its sources would not match this snapshot"
                asks[HERO][norm(q)] = data
                print(f"  asked: {q}\n     -> {data['answer'][:100]!r}")
            else:
                print(f"  could not ask '{q}': {res.status_code} {res.text[:120]}")

        snapshot = {
            "generated": datetime.now(timezone.utc).isoformat(),
            "note": "A recorded snapshot of the synthetic Sharma Foods demo, produced by the real pipeline. Read-only: actions need the backend.",
            "cases": listing, "details": details, "documents": documents, "crm": crm, "asks": asks, "settlements": settlements,
            "heroCase": HERO,
        }
        (OUT / "snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {OUT / 'snapshot.json'} ({(OUT / 'snapshot.json').stat().st_size // 1024} KB) and {len(documents[HERO])} PDFs")
        client.post(f"/api/cases/{HERO}/demo/reset")      # leaves no Cognee dataset behind


if __name__ == "__main__":
    main()
