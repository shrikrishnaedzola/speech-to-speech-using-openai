"""Call lifecycle, live metrics, review marks and export."""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import BACKEND_DIR, settings
from ..db import get_db
from ..models import Call, Review, TurnMetric
from ..schemas import CreateCallRequest, EndCallRequest, ReviewRequest, TurnRequest
from ..services import export
from ..services.call_state import build_call_report
from ..services.forms import load_form
from ..services.report_bridge import generate_report_safely

AUDIO_DIR = BACKEND_DIR / "data" / "audio"  # git-ignored; dummy test calls only
MAX_AUDIO_BYTES = 30 * 1024 * 1024

router = APIRouter(prefix="/api/calls", tags=["calls"])


def _get_call(db: Session, call_id: int) -> Call:
    call = db.get(Call, call_id)
    if call is None:
        raise HTTPException(404, "Call not found")
    return call


@router.post("")
def create_call(body: CreateCallRequest, db: Session = Depends(get_db)):
    """Create a call record before connecting (also used by Simulate mode)."""
    if load_form(db, body.form_id) is None:
        raise HTTPException(404, "Form not found")
    model = {"live": settings.live_model, "realtime": settings.realtime_model, "simulate": "simulate"}[body.mode]
    default_rate = {"live": settings.cost_per_min_live, "realtime": settings.cost_per_min_realtime, "simulate": 0.0}
    call = Call(
        form_id=body.form_id,
        mode=body.mode,
        model=model,
        delegate_model=(body.delegate_model or settings.live_delegate_model) if body.mode == "live" else None,
        language=body.language,
        voice=body.voice,
        cost_rate_per_min=body.cost_rate_per_min if body.cost_rate_per_min is not None else default_rate[body.mode],
        audio_mode=body.audio_mode,
    )
    db.add(call)
    db.commit()
    return {"call_id": call.id, "model": call.model, "delegate_model": call.delegate_model}


@router.get("/{call_id}")
def get_call(call_id: int, db: Session = Depends(get_db)):
    call = _get_call(db, call_id)
    return build_call_report(db, call, load_form(db, call.form_id))


@router.post("/{call_id}/turns")
def add_turn(call_id: int, body: TurnRequest, db: Session = Depends(get_db)):
    """Save one response-time measurement (measured in the browser)."""
    _get_call(db, call_id)
    count = db.scalar(select(func.count()).select_from(TurnMetric).where(TurnMetric.call_id == call_id))
    db.add(TurnMetric(call_id=call_id, turn_index=count + 1, latency_ms=body.latency_ms, ts_ms=body.ts_ms))
    db.commit()
    return {"turn_index": count + 1}


@router.post("/{call_id}/end")
def end_call(call_id: int, body: EndCallRequest, db: Session = Depends(get_db)):
    call = _get_call(db, call_id)
    call.status = "failed" if body.failed else "ended"
    call.ended_at = datetime.now(timezone.utc)
    call.duration_s = body.duration_s
    call.interruptions = body.interruptions
    call.usage_seconds = body.usage_seconds
    call.transcript_json = json.dumps(body.transcript, ensure_ascii=False)
    call.client_started_at = body.client_started_at
    call.events_json = json.dumps(body.events)
    db.commit()
    result = build_call_report(db, call, load_form(db, call.form_id))
    # Post-call report is generated automatically when the call ends.
    result["report_ready"] = generate_report_safely(call.id)
    return result


@router.post("/{call_id}/audio")
async def upload_agent_audio(call_id: int, request: Request, db: Session = Depends(get_db)):
    """Save the agent's voice as WAV (sent by the browser after the call) and refresh the report.

    Used for the optional MOS voice-quality score. Dummy test calls only.
    """
    if not settings.agent_audio:
        raise HTTPException(501, "Agent audio recording is turned off on this deployment.")
    call = _get_call(db, call_id)
    body = await request.body()
    if not body.startswith(b"RIFF") or len(body) > MAX_AUDIO_BYTES:
        raise HTTPException(400, "Expected a WAV file under 30 MB")
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIO_DIR / f"call_{call.id}_agent.wav"
    path.write_bytes(body)
    call.agent_audio_path = str(path)
    db.commit()
    return {"saved": True, "report_ready": generate_report_safely(call.id)}


@router.post("/{call_id}/review")
def save_review(call_id: int, body: ReviewRequest, db: Session = Depends(get_db)):
    """Save the tester's Correct/Wrong mark for one field (mark=None removes it)."""
    call = _get_call(db, call_id)
    row = db.scalar(select(Review).where(Review.call_id == call_id, Review.field_id == body.field_id))
    if body.mark is None:
        if row:
            db.delete(row)
    else:
        if row is None:
            row = Review(call_id=call_id, field_id=body.field_id)
            db.add(row)
        row.mark = body.mark
        row.expected_value = body.expected_value
    db.commit()
    return build_call_report(db, call, load_form(db, call.form_id))


@router.get("/{call_id}/export")
def export_call(call_id: int, format: str = Query("json", pattern="^(json|csv)$"), db: Session = Depends(get_db)):
    call = _get_call(db, call_id)
    report = build_call_report(db, call, load_form(db, call.form_id))
    filename = f"call_{call_id}_report.{format}"
    if format == "csv":
        content, media = export.to_csv(report), "text/csv"
    else:
        content, media = export.to_json(report), "application/json"
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
