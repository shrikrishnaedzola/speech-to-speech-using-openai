"""FastAPI entry point. Run from backend/:  uvicorn app.main:app --reload --port 8000"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .config import LANGUAGES, VOICES, settings
from .db import Base, SessionLocal, add_missing_columns, check_mysql_charset, describe_db_error, engine
from .routers import calls, forms, session, tools
from .services import report_bridge
from .services.forms import seed_forms

# Show our own warnings (e.g. the OpenAI error reason) in the uvicorn terminal.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")


log = logging.getLogger(__name__)

# Set when the database could not be prepared. The app keeps running so
# /api/config can show the reason in the UI instead of a bare "500".
startup_error: str | None = None
_last_attempt = 0.0
RETRY_AFTER_S = 5  # while broken, try the database setup again at most this often


def init_database(attempts: int = 3) -> None:
    """Create tables, add new columns and load forms. Safe to run many times.

    On Vercel several instances can start at the same moment and race to create
    the same tables ("Table 'forms' already exists"). Running again fixes that,
    because the second run sees the tables and skips them.
    """
    global startup_error, _last_attempt
    _last_attempt = time.monotonic()
    for attempt in range(1, attempts + 1):
        try:
            if warning := check_mysql_charset():
                log.warning(warning)
            Base.metadata.create_all(engine)  # only creates missing tables
            add_missing_columns()  # upgrade an older database for the post-call report
            with SessionLocal() as db:
                seed_forms(db, settings.seed_forms_dir)
            startup_error = None
            return
        except Exception as exc:
            startup_error = describe_db_error(exc)
            if attempt < attempts:
                log.warning("Database setup attempt %s failed, retrying: %s", attempt, startup_error)
                time.sleep(0.5 * attempt)
    log.error("DATABASE STARTUP FAILED: %s", startup_error)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Only says whether a key is present, never prints it.
    log.info("OPENAI_API_KEY configured: %s · database: %s", bool(settings.openai_api_key), engine.dialect.name)
    await run_in_threadpool(init_database)
    yield


app = FastAPI(title="Zolabs Voice Form Tester", lifespan=lifespan)


@app.middleware("http")
async def database_ready(request: Request, call_next):
    """If the database is not ready, retry the setup now and then; until it works,
    answer API calls with the reason (except /api/config, which shows it in the UI)."""
    if startup_error and time.monotonic() - _last_attempt > RETRY_AFTER_S:
        await run_in_threadpool(init_database, 1)
    if startup_error and request.url.path.startswith("/api/") and request.url.path != "/api/config":
        return JSONResponse({"detail": f"Database not ready: {startup_error}"}, status_code=503)
    return await call_next(request)


# The Vite dev server proxies /api, but allow direct calls from it too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(forms.router)
app.include_router(session.router)
app.include_router(tools.router)
app.include_router(calls.router)
app.include_router(report_bridge.router)  # post-call report (shared report_module)


@app.get("/api/config")
def get_config():
    """Dropdown options and defaults for the UI. Never includes the API key."""
    return {
        "models": [
            {"mode": "live", "model": settings.live_model, "delegate_model": settings.live_delegate_model},
            {"mode": "realtime", "model": settings.realtime_model},
        ],
        "languages": LANGUAGES,
        "voices": VOICES,
        "cost_per_min": {"live": settings.cost_per_min_live, "realtime": settings.cost_per_min_realtime},
        "live_init_seconds": settings.live_init_seconds,
        "api_key_configured": bool(settings.openai_api_key),
        "startup_error": startup_error,  # database problem at startup (password removed), else null
        # Turned off on Vercel (see config.py); the UI hides these when false.
        "features": {"pdf_export": settings.pdf_export, "agent_audio": settings.agent_audio},
    }
