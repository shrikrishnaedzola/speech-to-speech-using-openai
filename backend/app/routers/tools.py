"""POST /api/tools/{tool_name} - run a tool call from the voice agent.

The browser receives the function call from OpenAI, posts it here, and sends
the returned `output` string back to the model.
"""
import json
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Call, ToolCall
from ..schemas import ToolRequest
from ..services.forms import load_form
from ..services.report_bridge import generate_report_safely
from ..services.tools import TOOL_NAMES, run_tool

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.post("/{tool_name}")
def handle_tool(tool_name: str, body: ToolRequest, db: Session = Depends(get_db)):
    if tool_name not in TOOL_NAMES:
        raise HTTPException(404, f"Unknown tool {tool_name}")
    call = db.get(Call, body.call_id)
    if call is None:
        raise HTTPException(404, "Call not found")
    form = load_form(db, call.form_id)

    started = time.perf_counter()
    try:
        result = run_tool(db, call, form, tool_name, body.arguments)
    except Exception as exc:  # never crash the call; tell the agent instead
        db.rollback()
        result = {"ok": False, "error": f"Server error: {exc}"}
    duration_ms = (time.perf_counter() - started) * 1000

    db.add(ToolCall(
        call_id=call.id,
        name=tool_name,
        arguments_json=json.dumps(body.arguments),
        success=bool(result.get("ok")),
        result_json=json.dumps(result),
        duration_ms=duration_ms,
    ))
    db.commit()
    # complete_form succeeded: generate the post-call report now (regenerated again on End Call).
    if tool_name == "complete_form" and result.get("ok"):
        generate_report_safely(call.id)
    return {"ok": bool(result.get("ok")), "result": result, "output": json.dumps(result), "duration_ms": duration_ms}
