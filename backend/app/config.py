"""App settings, read from environment variables (.env at the repo root).

The OpenAI key is only read here and only used by services/openai_session.py.
It is never returned by any API endpoint and never logged.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent  # .../backend
load_dotenv(BACKEND_DIR.parent / ".env")


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _api_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    # Treat the .env.example placeholder as "not set".
    return "" if key in ("", "sk-your-key-here") else key


class Settings:
    openai_api_key: str = _api_key()
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    live_model: str = os.getenv("LIVE_MODEL", "gpt-live-1")
    realtime_model: str = os.getenv("REALTIME_MODEL", "gpt-realtime-2.1")
    live_delegate_model: str = os.getenv("LIVE_DELEGATE_MODEL", "gpt-5.6-terra")
    realtime_transcribe_model: str = os.getenv("REALTIME_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")

    cost_per_min_live: float = _float("COST_PER_MIN_LIVE", 0.05)
    cost_per_min_realtime: float = _float("COST_PER_MIN_REALTIME", 0.10)
    live_init_seconds: float = _float("LIVE_INIT_SECONDS", 15)

    # Local: SQLite file (relative paths are resolved from backend/).
    # Deployed: MySQL, e.g. mysql+pymysql://USER:PASSWORD@HOST:3306/DBNAME?charset=utf8mb4
    # Set it as an environment variable in Vercel - never commit it.
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    # true = connect to MySQL over TLS (most hosted MySQL servers require it).
    database_ssl: bool = os.getenv("DATABASE_SSL", "false").lower() == "true"

    # Vercel sets VERCEL=1. There the disk is read-only and Chromium does not fit,
    # so PDF export and agent-audio recording are turned off by default.
    on_vercel: bool = os.getenv("VERCEL") == "1"
    pdf_export: bool = os.getenv("PDF_EXPORT", "off" if on_vercel else "on").lower() == "on"
    agent_audio: bool = os.getenv("AGENT_AUDIO", "off" if on_vercel else "on").lower() == "on"

    seed_forms_dir: Path = BACKEND_DIR / "seed_forms"


settings = Settings()

# Options shown in the UI dropdowns.
LANGUAGES = ["English", "Hindi", "Tamil", "Telugu", "Marathi", "Kannada", "Bengali"]

# Voice lists differ per model in the docs, so keep them separate.
# GPT-Live: set at startup with audio.output.voice (default "marin").
VOICES = {
    "live": ["marin", "cedar", "alloy", "ash", "ballad", "coral", "echo"],
    "realtime": ["marin", "cedar", "alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse"],
}
