"""Demo-day preflight: one command that says whether the whole demo will work, and what to fix if not.

    python scripts/demo_preflight.py            (from backend/, with the backend running)

Checks, in the order the demo needs them: backend, database health, settings, n8n and its four webhooks, Cognee, Sarvam credit, the demo pack and its
recorded Sarvam results (what works with DEMO_MODE=true when the network or the credit fails), and the demo cases being in their starting state.
Nothing is changed and no case data is read beyond counts. Secrets are never printed. Exit code 1 if anything FAILS.
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import config  # noqa: E402

BACKEND = f"http://localhost:{config.PORT}"
N8N = "http://localhost:5678"
rows: list[tuple[str, str, str]] = []


def add(status: str, what: str, detail: str = "") -> None:
    rows.append((status, what, detail))


def ok(what, detail=""): add("PASS", what, detail)
def warn(what, detail=""): add("WARN", what, detail)
def fail(what, detail=""): add("FAIL", what, detail)


def get(url: str, **kw):
    return httpx.get(url, timeout=kw.pop("timeout", 8), **kw)


# ------------------------------------------------------------------ 1. backend and database
def check_backend() -> dict | None:
    try:
        r = get(f"{BACKEND}/api/health")
        r.raise_for_status()
        ok("Backend is up", f"{BACKEND} (memory: {r.json().get('memory', {}).get('mode', '?')})")
    except Exception as e:  # noqa: BLE001
        fail("Backend is not answering", f"{BACKEND}: {type(e).__name__}. Start backend\\run.bat")
        return None
    try:
        con = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True, timeout=5)
        res = con.execute("PRAGMA quick_check").fetchone()[0]
        con.close()
        (ok if res == "ok" else fail)("Database file is healthy" if res == "ok" else "Database file is damaged",
                                      "" if res == "ok" else f"{res}. Stop the backend, rename karyakarta.db to karyakarta.db.bad and start it again (it reseeds).")
    except Exception as e:  # noqa: BLE001
        fail("Database could not be opened read-only", f"{type(e).__name__}: {e}")
    return {}


# ------------------------------------------------------------------ 2. settings (presence only, never values)
def check_settings() -> None:
    def flag(cond, good, bad, level="FAIL"):
        add("PASS" if cond else level, good if cond else bad, "")
    flag(config.CPV_ALLOW_DEMO_REFERENCE, "Demo controls are on (CPV_ALLOW_DEMO_REFERENCE=true): demo upload, reference point, resets, spike",
         "Demo controls are OFF: set CPV_ALLOW_DEMO_REFERENCE=true in backend/.env and restart", "WARN")
    flag(bool(config.SARVAM_AGENT_ID and config.SARVAM_AGENT_API_KEY), "Voice Chase agent is configured", "SARVAM_AGENT_ID / agent key missing: Voice Chase will not call", "WARN")
    flag(bool(config.SARVAM_VCIP_AGENT_ID), "V-CIP agent is configured", "SARVAM_VCIP_AGENT_ID missing: the V-CIP pre-interview call will be refused", "WARN")
    flag(bool(config.SARVAM_CONNECTION_ID and config.SARVAM_AGENT_PHONE_NUMBER), "Outbound calling is configured (Twilio connection and number)",
         "Outbound calling is not configured: use the voice probe as the fallback", "WARN")
    flag(bool(config.COGNEE_API_KEY and config.COGNEE_BASE_URL), "Cognee is configured", "COGNEE_* missing: no merchant twin", "FAIL")
    for name, url in (("documents", config.N8N_WEBHOOK_URL), ("voice chase", config.N8N_VOICE_WEBHOOK_URL), ("shop verification", config.N8N_CPV_WEBHOOK_URL),
                      ("settlement agent", config.N8N_SETTLEMENT_WEBHOOK_URL)):
        flag(bool(url), f"n8n webhook for {name} is set", f"N8N webhook for {name} is empty: the backend will run that step itself (works, but n8n is not shown)", "WARN")
    ok("Public app URL", config.PUBLIC_APP_URL + ("  (a phone needs https: use a tunnel)" if config.PUBLIC_APP_URL.startswith("http://") else ""))
    (ok if config.DEMO_MODE else warn)("DEMO_MODE=" + str(config.DEMO_MODE).lower(),
                                       "recorded Sarvam results are served first" if config.DEMO_MODE else "live Sarvam is used (needs credit and network); set DEMO_MODE=true for a fully safe demo")


# ------------------------------------------------------------------ 3. n8n
def check_n8n() -> None:
    try:
        r = get(f"{N8N}/healthz")
        (ok if r.status_code == 200 else fail)("n8n is up" if r.status_code == 200 else f"n8n answered {r.status_code}", N8N)
    except Exception as e:  # noqa: BLE001
        fail("n8n is not answering", f"{N8N}: {type(e).__name__}. docker start n8n")
        return
    for name, url in (("documents", config.N8N_WEBHOOK_URL), ("voice chase", config.N8N_VOICE_WEBHOOK_URL), ("voice result", config.N8N_VOICE_WEBHOOK_URL.replace("voice-chase", "voice-result")),
                      ("shop verification", config.N8N_CPV_WEBHOOK_URL), ("shop captured", config.N8N_CPV_WEBHOOK_URL.replace("cpv-start", "cpv-captured")),
                      ("settlement agent", config.N8N_SETTLEMENT_WEBHOOK_URL)):
        if not url:
            continue
        try:
            msg = get(url).text          # a GET never runs the workflow; a registered POST webhook answers "not registered for GET"
        except Exception as e:  # noqa: BLE001
            fail(f"n8n webhook '{name}' not reachable", type(e).__name__)
            continue
        if "not registered for GET" in msg or "Did you mean to make a POST" in msg:
            ok(f"n8n webhook '{name}' is registered")
        else:
            fail(f"n8n webhook '{name}' is NOT registered", "publish the workflow and restart n8n; allow ~20 s (see backend/n8n/README.md)")


# ------------------------------------------------------------------ 4. Cognee and Sarvam
def check_services() -> None:
    try:
        from app.memory import get_store
        h = get_store().health()
        (ok if h.get("available") else fail)("Cognee is reachable" if h.get("available") else "Cognee is not reachable", str(h.get("detail", "")))
    except Exception as e:  # noqa: BLE001
        fail("Cognee check failed", f"{type(e).__name__}: {e}"[:160])
    if not config.SARVAM_AGENT_API_KEY:
        fail("No Sarvam key", "SARVAM_API_KEY missing")
        return
    try:
        from app.sarvam.client import client
        client().text.transliterate(input="नमस्ते", source_language_code="hi-IN", target_language_code="en-IN")
        ok("Sarvam answers and has credit (checked with a tiny transliteration call)")
    except Exception as e:  # noqa: BLE001
        text = str(e)
        if "402" in text or "Insufficient credit" in text or "Payment" in type(e).__name__:
            fail("Sarvam is OUT OF CREDIT (402)", "top up in the Sarvam console. Until then only documents with a recorded result (see below) can be read: keep DEMO_MODE=true")
        else:
            warn("Sarvam check failed", f"{type(e).__name__}: {text[:120]}")


# ------------------------------------------------------------------ 5. the demo pack and recorded results
def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_pack() -> None:
    root = Path(__file__).resolve().parent.parent
    pack, fixes, cache = root / "seed" / "demo_pack", root / "seed" / "demo_pack" / "fixes", root / "demo_cache"
    docs, fx = sorted(pack.glob("*.pdf")), sorted(fixes.glob("*.pdf"))
    (ok if len(docs) == 9 else fail)(f"Demo pack has {len(docs)}/9 documents", str(pack) if len(docs) != 9 else "")
    (ok if len(fx) == 4 else warn)(f"Fix pack has {len(fx)}/4 documents", "" if len(fx) == 4 else "python -m seed.make_realistic_docs")

    def recorded(p: Path) -> bool:
        h = sha(p)
        return (cache / f"{h}.digitise.json").exists() and any(cache.glob(f"{h}.extract-*.json"))
    miss = [p.name for p in docs if not recorded(p)]
    (ok if not miss else fail)("Every demo document has a recorded Sarvam result (works offline / without credit)" if not miss else f"{len(miss)} demo document(s) have NO recorded Sarvam result",
                               ", ".join(miss) + ". Run: seed.bat --refresh-cache (needs Sarvam credit)" if miss else "")
    miss_fx = [p.name for p in fx if not recorded(p)]
    (ok if not miss_fx else warn)("Fix pack documents have recorded results" if not miss_fx else f"{len(miss_fx)} fix-pack document(s) have no recorded Sarvam result",
                                  ", ".join(miss_fx) + ". With Sarvam credit: seed.bat --record-fixes. Without it, they can only be read live." if miss_fx else "")
    photos = list((root / "seed" / "shop").glob("*.jpg"))
    (ok if len(photos) >= 3 else warn)(f"Printable shop photos: {len(photos)}", "python -m seed.make_shop_photos" if len(photos) < 3 else "print them; never show them on a screen")


# ------------------------------------------------------------------ 6. the demo cases are in their starting state
def check_cases() -> None:
    try:
        items = {r["id"]: r for r in get(f"{BACKEND}/api/cases").json()["data"]["items"]}
    except Exception as e:  # noqa: BLE001
        fail("Could not read the cases", type(e).__name__)
        return
    s = items.get("KYB-20814")
    if s is None:
        fail("Sharma Foods (KYB-20814) is missing", "restart the backend; it reseeds an empty database")
    elif s["docProgress"]["uploaded"] or s["stageNumber"] != 2:
        warn("Sharma Foods has data from a previous run", f"stage {s['stageNumber']}, {s['docProgress']['uploaded']} document(s). Open it as KAM and press 'Reset demo case', or run scripts/demo_reset_all.py")
    else:
        ok("Sharma Foods is at its starting state (no documents)")
    a = items.get("KYB-20820")
    if a is None:
        warn("Settlement demo merchant (KYB-20820) is missing", "restart the backend (FINOPS_SEED_DEMO=true) and run python -m seed.seed_settlements")
    else:
        try:
            d = get(f"{BACKEND}/api/cases/KYB-20820/settlements").json()["data"]
            h = d["detection"]["health"]
            (ok if h == "healthy" and not d["investigation"] else warn)("Annapurna Sweets (KYB-20820) ledger is healthy, nothing open" if h == "healthy" and not d["investigation"] else f"Annapurna Sweets is '{h}'" + (" with an open investigation" if d["investigation"] else ""),
                                                                      "" if h == "healthy" and not d["investigation"] else "open it > Settlements > Reset, or run scripts/demo_reset_all.py")
        except Exception as e:  # noqa: BLE001
            warn("Could not read the settlement ledger", type(e).__name__)


def main() -> None:
    if check_backend() is None:
        print_report()
        return
    check_settings()
    check_n8n()
    check_services()
    check_pack()
    check_cases()
    print_report()


def print_report() -> None:
    icon = {"PASS": "✔", "WARN": "⚠", "FAIL": "✘"}
    for st, what, detail in rows:
        print(f" {icon[st]} {what}" + (f"\n     {detail}" if detail else ""))
    n = {k: sum(1 for r in rows if r[0] == k) for k in icon}
    print(f"\n{n['PASS']} passed · {n['WARN']} warnings · {n['FAIL']} failed")
    print("READY for the demo." if not n["FAIL"] and not n["WARN"] else "Fix the failures first; warnings are things to know before you present." if n["FAIL"] else "Ready, with the warnings above to be aware of.")
    sys.exit(1 if n["FAIL"] else 0)


if __name__ == "__main__":
    main()
