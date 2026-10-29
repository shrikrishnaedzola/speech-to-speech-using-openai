"""FastAPI entry point. Run from backend/:  uvicorn app.main:app --reload --port 8000"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import LANGUAGES, VOICES, settings
from .db import Base, SessionLocal, add_missing_columns, engine
from .routers import calls, forms, session, tools
from .services import report_bridge
from .services.forms import seed_forms

# Show our own warnings (e.g. the OpenAI error reason) in the uvicorn terminal.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables and load all forms from seed_forms/*.json on startup.
    Base.metadata.create_all(engine)
    add_missing_columns()  # upgrade an older data/app.db for the post-call report
    with SessionLocal() as db:
        seed_forms(db, settings.seed_forms_dir)
    # Only says whether a key is present, never prints it.
    logging.getLogger(__name__).info("OPENAI_API_KEY configured: %s", bool(settings.openai_api_key))
    yield


app = FastAPI(title="Zolabs Voice Form Tester", lifespan=lifespan)

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
    }
