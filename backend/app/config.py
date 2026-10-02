"""Central settings. Everything comes from .env; nothing secret lives in code."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


PORT = int(os.environ.get("PORT", "8765"))
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
DEMO_MODE = _bool("DEMO_MODE")

DB_PATH = Path(os.environ.get("KARYAKARTA_DB", BASE_DIR / "karyakarta.db"))
STORAGE_DIR = Path(os.environ.get("KARYAKARTA_STORAGE", BASE_DIR / "storage"))
STORAGE_DIR.mkdir(exist_ok=True)

N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "").strip()
N8N_FALLBACK_INPROCESS = _bool("N8N_FALLBACK_INPROCESS", True)
PIPELINE_AUTORUN = _bool("PIPELINE_AUTORUN", True)   # false: uploads only store files (tests, manual runs)

COGNEE_MODE = os.environ.get("COGNEE_MODE", "cloud").strip().lower()
COGNEE_BASE_URL = os.environ.get("COGNEE_BASE_URL", "").rstrip("/")
COGNEE_TENANT_ID = os.environ.get("COGNEE_TENANT_ID", "")
COGNEE_USER_ID = os.environ.get("COGNEE_USER_ID", "")
COGNEE_API_KEY = os.environ.get("COGNEE_API_KEY", "")
COGNEE_TIMEOUT_SECONDS = float(os.environ.get("COGNEE_TIMEOUT_SECONDS", "60"))

# Sarvam Samvaad voice agent (Voice Chase). Org / workspace ids are not secret; the key is.
SARVAM_ORG_ID = os.environ.get("SARVAM_ORG_ID", "019f298f-eba1-725a-a645-5db63306d773")
SARVAM_WORKSPACE_ID = os.environ.get("SARVAM_WORKSPACE_ID", "019f298f-eba7-7b7a-8f83-a767c766c059")
SARVAM_AGENT_ID = os.environ.get("SARVAM_AGENT_ID", "").strip()
SARVAM_AGENT_API_KEY = (os.environ.get("SARVAM_API_KEY_NEW_FOR_VOICE", "").strip()
                        or os.environ.get("SARVAM_AGENT_API_KEY", "").strip()
                        or os.environ.get("SARVAM_API_KEY", ""))
N8N_VOICE_WEBHOOK_URL = os.environ.get("N8N_VOICE_WEBHOOK_URL", "").strip()

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
