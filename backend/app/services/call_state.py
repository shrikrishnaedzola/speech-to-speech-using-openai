"""Build the full state of one call: field cards, scores, metrics and cost.

Used by GET /api/calls/{id} and by the export endpoint, so the UI and the
exported report always show the same numbers.
"""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Answer, Call, Review, ToolCall, TurnMetric
from . import form_logic

# Statuses that count as "has a value" for follow-up logic and scoring.
VALUE_STATUSES = {"filled", "needs_confirmation"}


def answer_rows(db: Session, call_id: int) -> dict[str, Answer]:
    rows = db.scalars(select(Answer).where(Answer.call_id == call_id)).all()
    return {row.field_id: row for row in rows}


def answers_map(rows: dict[str, Answer]) -> dict:
    """field_id -> parsed value, for fields that currently have a value."""
    return {
        field_id: json.loads(row.value_json)
        for field_id, row in rows.items()
        if row.status in VALUE_STATUSES and row.value_json is not None
    }


def next_field(form: dict, rows: dict[str, Answer]) -> dict | None:
    """First active field that is still pending (no answer and not skipped)."""
    values = answers_map(rows)
    for field in form_logic.active_fields(form, values):
        if field["id"] not in rows:
            return field
    return None


def estimate_cost(call: Call) -> dict:
    """Cost estimate. Prefers billed seconds reported by OpenAI, else call duration."""
    seconds = call.usage_seconds if call.usage_seconds is not None else (call.duration_s or 0)
    basis = "usage_seconds" if call.usage_seconds is not None else "duration"
    if call.mode == "live" and call.usage_seconds is None and call.duration_s:
        seconds += settings.live_init_seconds  # WebRTC session init is billed as 15s
    return {
        "billable_seconds": round(seconds, 1),
        "rate_per_min": call.cost_rate_per_min,
        "estimated_usd": round(seconds / 60 * call.cost_rate_per_min, 4),
        "basis": basis,
        "note": "Voice minutes only. Delegated backend model tokens (GPT-Live) are billed separately.",
    }


def build_call_report(db: Session, call: Call, form: dict) -> dict:
    rows = answer_rows(db, call.id)
    values = answers_map(rows)
    reviews = {r.field_id: r for r in db.scalars(select(Review).where(Review.call_id == call.id))}

    # ----- field cards (Column 2) -----
    fields = []
    for field in form["fields"]:
        row = rows.get(field["id"])
        review = reviews.get(field["id"])
        fields.append({
            "id": field["id"],
            "label": field.get("label", field["id"]),
            "type": field["type"],
            "required": bool(field.get("required")),
            "condition": form_logic.describe_condition(field["condition"]) if field.get("condition") else None,
            "active": form_logic.is_active(field, values),
            "status": row.status if row else "pending",
            "value": json.loads(row.value_json) if row and row.value_json else None,
            "raw_value": row.raw_value if row else None,
            "confidence": row.confidence if row else None,
            "reason": row.reason if row else None,
            "review": {"mark": review.mark, "expected_value": review.expected_value} if review else None,
        })

    active = [f for f in fields if f["active"]]
    filled = [f for f in active if f["status"] in VALUE_STATUSES and f["value"] is not None]
    correct = [f for f in filled if f["review"] and f["review"]["mark"] == "correct"]
    reviewed = [f for f in filled if f["review"]]
    required = [f for f in active if f["required"]]
    required_filled = [f for f in required if f in filled]

    # ----- metrics (Column 3) -----
    turns = db.scalars(select(TurnMetric).where(TurnMetric.call_id == call.id).order_by(TurnMetric.turn_index)).all()
    latencies = [t.latency_ms for t in turns]
    tool_calls = db.scalars(select(ToolCall).where(ToolCall.call_id == call.id).order_by(ToolCall.id)).all()

    return {
        "call": {
            "id": call.id,
            "form_id": call.form_id,
            "mode": call.mode,
            "model": call.model,
            "delegate_model": call.delegate_model,
            "language": call.language,
            "voice": call.voice,
            "status": call.status,
            "form_completed": call.form_completed,
            "started_at": call.started_at.isoformat() if call.started_at else None,
            "ended_at": call.ended_at.isoformat() if call.ended_at else None,
            "duration_s": call.duration_s,
        },
        "form": {"id": form["id"], "name": form["name"]},
        "fields": fields,
        "scores": {
            "filled_fields": len(filled),
            "reviewed_fields": len(reviewed),
            "correct_fields": len(correct),
            "accuracy": round(len(correct) / len(filled), 3) if filled else None,
            "required_total": len(required),
            "required_filled": len(required_filled),
            "completion": round(len(required_filled) / len(required), 3) if required else None,
        },
        "metrics": {
            "turns": len(turns),
            "turn_latencies_ms": [{"turn": t.turn_index, "latency_ms": round(t.latency_ms)} for t in turns],
            "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
            "max_latency_ms": round(max(latencies)) if latencies else None,
            "interruptions": call.interruptions,
            "duration_s": call.duration_s,
            "usage_seconds": call.usage_seconds,
        },
        "cost": estimate_cost(call),
        "tool_calls": [
            {
                "id": t.id,
                "name": t.name,
                "arguments": json.loads(t.arguments_json),
                "success": t.success,
                "result": json.loads(t.result_json),
                "duration_ms": round(t.duration_ms, 1),
                "created_at": t.created_at.isoformat(),
            }
            for t in tool_calls
        ],
        "transcript": json.loads(call.transcript_json or "[]"),
    }
