import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


DEMO_MODE = _bool("DEMO_MODE", True)
ESCALATE_SECONDS = int(os.getenv("ESCALATE_SECONDS") or 60)

NTS_SERVICE_KEY = os.getenv("NTS_SERVICE_KEY", "").strip()
GOOGLE_SAFE_BROWSING_KEY = os.getenv("GOOGLE_SAFE_BROWSING_KEY", "").strip()
VIRUSTOTAL_API_KEY = os.getenv("VIRUSTOTAL_API_KEY", "").strip()
FOODSAFETY_API_KEY = os.getenv("FOODSAFETY_API_KEY", "").strip()
FTC_CSV_PATH = BASE_DIR / (os.getenv("FTC_CSV_PATH") or "data/telecom_sellers.csv")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()

DB_PATH = BASE_DIR / "data" / "callguard.db"
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
