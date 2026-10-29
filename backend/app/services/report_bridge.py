"""Connects this tester to the shared report_module.

report_module needs four functions (see report_module/api.py). They read and
write this tester's own SQLite tables. Each opens its own DB session because
they are called from report_module's routes, outside our get_db dependency.
"""
import json
import logging

from report_module.adapters.openai_tester import to_call_data
from report_module.api import make_report_router
from report_module.call_data import CallData, Ratings
from sqlalchemy import select

from ..db import SessionLocal
from ..models import Call, CallRatings, CallReport, TurnMetric
from .call_state import build_call_report
from .forms import load_form

log = logging.getLogger(__name__)


def get_call_data(call_id: str) -> CallData | None:
    with SessionLocal() as db:
        call = db.get(Call, int(call_id)) if call_id.isdigit() else None
        if call is None:
            return None
        tester_report = build_call_report(db, call, load_form(db, call.form_id))
        turn_ts = {t.turn_index: t.ts_ms for t in db.scalars(select(TurnMetric).where(TurnMetric.call_id == call.id))}
        ratings = db.get(CallRatings, call.id)
        return to_call_data(tester_report, extras={
            "client_started_at": call.client_started_at,
            "audio_mode": call.audio_mode,
            "events": json.loads(call.events_json or "[]"),
            "turn_ts_ms": turn_ts,
            "ratings": json.loads(ratings.ratings_json) if ratings else None,
            "agent_audio_path": call.agent_audio_path,
        })


def save_report(call_id: str, report: dict) -> None:
    with SessionLocal() as db:
        row = db.get(CallReport, int(call_id)) or CallReport(call_id=int(call_id))
        row.report_json = json.dumps(report, ensure_ascii=False)
        db.merge(row)
        db.commit()


def load_report(call_id: str) -> dict | None:
    with SessionLocal() as db:
        row = db.get(CallReport, int(call_id)) if call_id.isdigit() else None
        return json.loads(row.report_json) if row else None


def save_ratings(call_id: str, ratings: Ratings) -> None:
    with SessionLocal() as db:
        row = db.get(CallRatings, int(call_id)) or CallRatings(call_id=int(call_id))
        row.ratings_json = ratings.model_dump_json()
        db.merge(row)
        db.commit()


router = make_report_router(
    get_call_data=get_call_data,
    save_report=save_report,
    load_report=load_report,
    save_ratings=save_ratings,
)


def generate_report_safely(call_id: int) -> bool:
    """Auto-generate the report (End Call / complete_form). Never breaks the call if it fails."""
    try:
        router.generate_report(str(call_id))
        return True
    except Exception:
        log.exception("Post-call report generation failed for call %s", call_id)
        return False
