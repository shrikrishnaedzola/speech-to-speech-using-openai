"""Latency: how long the caller waits for the agent to reply."""
import math

from .call_data import CallData


def percentile(values: list[float], pct: float) -> float | None:
    """Nearest-rank percentile (simple and easy to explain): p90 = the value 90% of turns are at or below."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def rate_latency(ms: float | None, thresholds: dict) -> str | None:
    if ms is None:
        return None
    if ms < thresholds["good"]:
        return "Good"
    if ms <= thresholds["ok"]:
        return "OK"
    return "Poor"


def _context_for_turn(data: CallData, index: int) -> str:
    """What was happening before this reply: tool calls since the previous turn, length of the reply."""
    metrics = data.turn_metrics
    turn = metrics[index]
    notes = []
    if turn.ts_ms is not None:
        start = metrics[index - 1].ts_ms if index > 0 and metrics[index - 1].ts_ms is not None else turn.ts_ms - 15000
        tools = [c for c in data.tool_calls if c.ts_ms is not None and start <= c.ts_ms <= turn.ts_ms]
        if tools:
            names = ", ".join(f"{c.name}({c.arguments.get('field_id', '')})" + ("" if c.success else " failed") for c in tools)
            notes.append(f"tool call before reply: {names}")
        reply = next((t for t in data.transcript if t.role == "agent" and t.ts_ms is not None and t.ts_ms >= turn.ts_ms - 500), None)
        if reply and len(reply.text.split()) > 25:
            notes.append(f"long reply ({len(reply.text.split())} words)")
    if turn.stt_ms is not None or turn.llm_ms is not None:
        parts = {"STT": turn.stt_ms, "LLM": turn.llm_ms, "TTS": turn.tts_ms}
        slowest = max((k for k, v in parts.items() if v is not None), key=lambda k: parts[k])
        notes.append(f"slowest stage: {slowest} ({round(parts[slowest])} ms)")
    return "; ".join(notes) or "no extra activity recorded"


def analyze_latency(data: CallData, settings: dict) -> dict:
    thresholds = settings["latency_thresholds_ms"]
    values = [m.latency_ms for m in data.turn_metrics]
    avg = sum(values) / len(values) if values else None
    has_split = any(m.stt_ms is not None or m.llm_ms is not None or m.tts_ms is not None for m in data.turn_metrics)

    slowest_idx = sorted(range(len(values)), key=lambda i: values[i], reverse=True)[:3]
    return {
        "turns": len(values),
        "avg_ms": round(avg) if avg is not None else None,
        "median_ms": round(median(values)) if values else None,
        "p90_ms": round(percentile(values, 90)) if values else None,
        "max_ms": round(max(values)) if values else None,
        "min_ms": round(min(values)) if values else None,
        "rating": rate_latency(avg, thresholds),
        "thresholds": thresholds,
        "per_turn": [
            {
                "turn": m.turn,
                "latency_ms": round(m.latency_ms),
                "rating": rate_latency(m.latency_ms, thresholds),
                "stt_ms": m.stt_ms, "llm_ms": m.llm_ms, "tts_ms": m.tts_ms,
            }
            for m in data.turn_metrics
        ],
        "has_stage_split": has_split,  # Sarvam: STT / LLM / TTS stacked bar
        "slowest": [
            {"turn": data.turn_metrics[i].turn, "latency_ms": round(values[i]), "context": _context_for_turn(data, i)}
            for i in slowest_idx
        ],
    }
