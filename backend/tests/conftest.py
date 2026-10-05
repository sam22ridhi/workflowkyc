import os
import sys
import tempfile
from pathlib import Path

# Isolated DB/storage and no external calls, set BEFORE the app is imported.
_tmp = tempfile.mkdtemp(prefix="karyakarta_test_")
os.environ["KARYAKARTA_DB"] = str(Path(_tmp) / "test.db")
os.environ["KARYAKARTA_STORAGE"] = str(Path(_tmp) / "storage")
os.environ["N8N_WEBHOOK_URL"] = ""
os.environ["COGNEE_API_KEY"] = ""
os.environ["DEMO_MODE"] = "false"
os.environ["SARVAM_API_KEY"] = ""      # tests must never reach the real Sarvam API
os.environ["PIPELINE_AUTORUN"] = "false"
os.environ["FINOPS_SEED_DEMO"] = "false"   # the settlement demo merchant is created explicitly by its own tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:   # runs lifespan -> creates tables + seeds 5 cases
        yield c
