import os
import sys
import tempfile
from pathlib import Path

# Isolated DB/storage and no external calls, set BEFORE the app is imported.
_tmp = tempfile.mkdtemp(prefix="karyakarta_test_")
os.environ["KARYAKARTA_DB"] = str(Path(_tmp) / "test.db")
os.environ["KARYAKARTA_STORAGE"] = str(Path(_tmp) / "storage")
for _name in ("N8N_WEBHOOK_URL", "N8N_VOICE_WEBHOOK_URL", "N8N_CPV_WEBHOOK_URL", "N8N_SETTLEMENT_WEBHOOK_URL"):
    os.environ[_name] = ""                  # tests never call a real n8n, whatever the developer's .env says
os.environ["COGNEE_API_KEY"] = ""
os.environ["DEMO_MODE"] = "false"
os.environ["SARVAM_API_KEY"] = ""      # tests must never reach the real Sarvam API
# Tests run on SQLite and local disk unless a Postgres is asked for explicitly (TEST_DATABASE_URL=postgresql://...). A developer's .env must never point them at a real Supabase.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "")
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_KEY"] = ""
os.environ["PIPELINE_AUTORUN"] = "false"
os.environ["FINOPS_SEED_DEMO"] = "false"   # the settlement demo merchant is created explicitly by its own tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    if os.environ["DATABASE_URL"]:                  # a Postgres test run starts from empty tables
        from sqlmodel import SQLModel
        from app.db import engine
        SQLModel.metadata.drop_all(engine)
    with TestClient(app) as c:   # runs lifespan -> creates tables + seeds 5 cases
        yield c
