"""Adapter for the OpenAI Voice Form Tester.

Input: the tester's own call report (GET /api/calls/{id} -> build_call_report())
plus a few extras the tester stores for reports. Output: CallData.

Use it as the template for the Sarvam / Gemini / ElevenLabs adapters:
map each of their fields onto the same CallData fields.
"""
from datetime import datetime, timezone

from ..call_data import CallData


def _parse_time(iso: str | None) -> datetime | None:
    """ISO text -> aware datetime. Times without a timezone (SQLite drops it) are UTC."""
    if not iso:
        return None
    try:
        when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _ms_since(start: datetime | None, iso: str | None) -> float | None:
    when = _parse_time(iso)
    if start is None or when is None:
        return None
    return round((when - start).total_seconds() * 1000)


def to_call_data(tester_report: dict, *, extras: dict) -> CallData:
    """
    tester_report: output of backend/app/services/call_state.build_call_report()
    extras: {
        "client_started_at": ISO time the browser connected (time zero),
        "audio_mode": "normal" | "phone_8khz",
        "events": [{"type": "barge_in", "ts_ms": ...}],
        "turn_ts_ms": {turn_index: ts_ms},
        "ratings": {...} | None,
        "agent_audio_path": str | None,
    }
    """
    call = tester_report["call"]
    start_iso = extras.get("client_started_at") or call.get("started_at")
    # Older calls have no browser start time; the call's created time is close enough.
    start = _parse_time(start_iso)
    model = call["model"] if call["mode"] != "simulate" else "simulate"

    turn_ts = extras.get("turn_ts_ms") or {}
    return CallData.model_validate({
        "call": {
            "call_id": str(call["id"]),
            "provider": "openai",
            "model": model,
            "voice": call.get("voice"),
            "language": call["language"],
            "audio_mode": extras.get("audio_mode") or "normal",
            "started_at": start_iso or "",
            "duration_s": call.get("duration_s"),
            "form_name": tester_report["form"]["name"],
            "form_completed": call.get("form_completed", False),
        },
        "transcript": [
            {"role": t["role"], "text": t["text"], "ts_ms": _ms_since(start, t.get("ts"))}
            for t in tester_report.get("transcript", [])
        ],
        "fields": [
            {
                "id": f["id"],
                "label": f["label"],
                "type": f["type"],
                "required": f["required"],
                "condition": f["condition"],
                "active": f["active"],
                "status": f["status"],
                "saved_value": f["value"],
                "expected_value": (f.get("review") or {}).get("expected_value") or None,
                "review_mark": (f.get("review") or {}).get("mark"),
            }
            for f in tester_report["fields"]
        ],
        "turn_metrics": [
            {"turn": t["turn"], "latency_ms": t["latency_ms"], "ts_ms": turn_ts.get(t["turn"])}
            for t in tester_report["metrics"]["turn_latencies_ms"]
        ],
        "tool_calls": [
            {
                "name": t["name"],
                "arguments": t["arguments"],
                "success": t["success"],
                "result": t["result"],
                "duration_ms": t["duration_ms"],
                "ts_ms": _ms_since(start, t.get("created_at")),
            }
            for t in tester_report["tool_calls"]
        ],
        "usage": {"voice_seconds": tester_report["metrics"].get("usage_seconds")},
        "interruptions": tester_report["metrics"].get("interruptions") or 0,
        "events": extras.get("events") or [],
        "ratings": extras.get("ratings") or {},
        "agent_audio_path": extras.get("agent_audio_path"),
    })
