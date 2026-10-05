"""Create the synthetic post-onboarding demo merchant (Annapurna Sweets, KYB-20820) with its 32-day settlement ledger, and put its
declared profile into the merchant twin (Cognee) so the Settlement Agent can recall it.

    python -m seed.seed_settlements            # create (if missing) + store the profile in Cognee + build the graph
    python -m seed.seed_settlements --no-memory
    python -m seed.seed_settlements --reset    # healthy ledger again, open investigations closed

All data is synthetic. Cognee must be configured in backend/.env for the memory step.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlmodel import Session, select  # noqa: E402

from app import config, memory_service  # noqa: E402
from app.db import engine, init_db  # noqa: E402
from app.finops import ledger  # noqa: E402
from app.memory import get_store  # noqa: E402
from app.models import Case, Investigation  # noqa: E402


def main() -> None:
    init_db()
    with Session(engine) as s:
        if "--reset" in sys.argv:
            for inv in s.exec(select(Investigation).where(Investigation.merchant_case_id == ledger.DEMO_CASE_ID, Investigation.status == "open")):
                inv.status, inv.closed_by = "dismissed", "reset"
                s.add(inv)
                c = s.get(Case, inv.id)
                if c:
                    c.status = "closed"
                    s.add(c)
            s.commit()
            print("ledger:", ledger.generate(s, ledger.DEMO_CASE_ID, spike=False))
        else:
            print("created demo merchant" if ledger.ensure_demo_merchant(s) else "demo merchant already exists")
        if "--no-memory" in sys.argv:
            return
        case = s.get(Case, ledger.DEMO_CASE_ID)
        dataset = memory_service.dataset_name(case)
        folder = Path(config.STORAGE_DIR) / case.id / "profile"
        folder.mkdir(parents=True, exist_ok=True)
        text = ledger.profile_text(case)
        f = folder / "merchant_profile.txt"
        f.write_text(text, encoding="utf-8")
        store = get_store()
        res = store.add_document(dataset, file_path=str(f), filename=f.name, mime="text/plain", summary_text=text)
        print("stored profile in Cognee dataset", dataset, res.data_ids)
        out = store.cognify(dataset, wait=True)
        print("cognify:", out.status, out.detail[:120])
        case.graph_status = "ready" if out.status == "completed" else "building"
        s.add(case)
        s.commit()


if __name__ == "__main__":
    main()
