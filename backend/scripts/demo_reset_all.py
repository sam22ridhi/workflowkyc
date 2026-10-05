"""Put every demo case back to its starting state with one command, so the demo can be run again.

    python scripts/demo_reset_all.py            (from backend/, with the backend running and CPV_ALLOW_DEMO_REFERENCE=true)

* the five onboarding cases (KYB-20814 to KYB-20818): files, checks, calls, shop verification, V-CIP and their Cognee memory are removed
* the settlement demo merchant (KYB-20820): healthy ledger again, open investigations closed
Real data is never touched: these are the seeded, synthetic demo cases only.
"""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import config  # noqa: E402

BACKEND = f"http://localhost:{config.PORT}"


def post(path: str) -> tuple[int, str]:
    r = httpx.post(f"{BACKEND}{path}", timeout=120)
    try:
        body = r.json()
    except ValueError:
        body = {}
    return r.status_code, (body.get("detail") if r.status_code >= 400 else str((body.get("data") or {}).get("memory", "ok")))


def main() -> None:
    bad = 0
    for cid in ("KYB-20814", "KYB-20815", "KYB-20816", "KYB-20817", "KYB-20818"):
        code, msg = post(f"/api/cases/{cid}/demo/reset")
        print(f" {'✔' if code == 200 else '✘'} {cid}: {msg}")
        bad += code != 200
    code, msg = post("/api/cases/KYB-20820/settlements/demo/reset")
    print(f" {'✔' if code == 200 else '✘'} KYB-20820 settlement ledger: {msg}")
    bad += code != 200
    print("\nAll demo cases are back at their starting state." if not bad else "\nSome resets failed: is the backend running with CPV_ALLOW_DEMO_REFERENCE=true?")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
