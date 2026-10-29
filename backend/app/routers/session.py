"""POST /api/session - connect the browser to OpenAI without exposing the key.

The browser sends its WebRTC SDP offer. We create the OpenAI session with the
server-side key and return only the SDP answer (and the OpenAI session id).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Call
from ..schemas import SessionRequest
from ..services import openai_session
from ..services.forms import load_form

router = APIRouter(prefix="/api", tags=["session"])
log = logging.getLogger(__name__)


@router.post("/session")
async def create_session(body: SessionRequest, db: Session = Depends(get_db)):
    call = db.get(Call, body.call_id)
    if call is None:
        raise HTTPException(404, "Call not found")
    if call.mode == "simulate":
        raise HTTPException(400, "Simulate calls do not use OpenAI")
    form = load_form(db, call.form_id)

    try:
        if call.mode == "live":
            config = openai_session.build_live_session(form, call.language, call.voice, call.delegate_model)
            result = await openai_session.create_live_session(body.sdp, config)
        else:
            config = openai_session.build_realtime_session(form, call.language, call.voice)
            result = await openai_session.create_realtime_call(body.sdp, config)
    except openai_session.OpenAISessionError as exc:
        call.status = "failed"
        db.commit()
        log.warning("OpenAI session failed (%s): %s", exc.status_code, exc)
        raise HTTPException(502, f"OpenAI error ({exc.status_code}): {exc}")

    call.status = "connected"
    call.openai_session_id = result["session_id"]
    db.commit()
    # Only the SDP answer and ids go to the browser. No key, no token.
    return {"sdp": result["sdp"], "openai_session_id": result["session_id"], "mode": call.mode}
