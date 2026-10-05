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
# Outbound calling (Sarvam Instant Outbound + a connected Twilio number). The call result is polled, so no public URL is needed;
# SARVAM_CALLBACK_URL is optional (a publicly reachable URL Sarvam can POST the call-completed webhook to).
SARVAM_CONNECTION_ID = os.environ.get("SARVAM_CONNECTION_ID", "").strip()
SARVAM_AGENT_PHONE_NUMBER = os.environ.get("SARVAM_AGENT_PHONE_NUMBER", "").strip()
SARVAM_AGENT_VERSION = int(os.environ.get("SARVAM_AGENT_VERSION", "1") or 1)
SARVAM_CALLBACK_URL = os.environ.get("SARVAM_CALLBACK_URL", "").strip()
# V-CIP pre-interview: a SECOND Sarvam agent (its own prompt: randomized Hindi liveness questions). See voice/SARVAM_VCIP_AGENT_SETUP.md.
SARVAM_VCIP_AGENT_ID = os.environ.get("SARVAM_VCIP_AGENT_ID", "").strip()
SARVAM_VCIP_AGENT_VERSION = int(os.environ.get("SARVAM_VCIP_AGENT_VERSION", "") or SARVAM_AGENT_VERSION)

# Contact point verification (Drishti)
PUBLIC_APP_URL = os.environ.get("PUBLIC_APP_URL", "http://localhost:5173").rstrip("/")   # where merchants open the capture link (needs HTTPS on a phone)
N8N_CPV_WEBHOOK_URL = os.environ.get("N8N_CPV_WEBHOOK_URL", "").strip()
CPV_RADIUS_M = float(os.environ.get("CPV_RADIUS_M", "100"))
CPV_MAX_ACCURACY_M = float(os.environ.get("CPV_MAX_ACCURACY_M", "100"))
CPV_LINK_HOURS = float(os.environ.get("CPV_LINK_HOURS", "24"))
CPV_MAX_CLOCK_SKEW_S = float(os.environ.get("CPV_MAX_CLOCK_SKEW_S", "120"))
N8N_SETTLEMENT_WEBHOOK_URL = os.environ.get("N8N_SETTLEMENT_WEBHOOK_URL", "").strip()   # .../webhook/karyakarta-settlement-scan
FINOPS_SEED_DEMO = _bool("FINOPS_SEED_DEMO", True)                 # create the synthetic post-onboarding demo merchant at startup
CPV_ALLOW_DEMO_REFERENCE = _bool("CPV_ALLOW_DEMO_REFERENCE")   # lets a demo set where the shop "is" (clearly labelled demo)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
