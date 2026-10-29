"""Optional AI-written summary (section 10).

Safety rules:
- The LLM gets ONLY the computed metrics and the already-masked transcript.
- After it answers, every number in its text is checked against the numbers we
  sent. Any number we did not send is listed as "unverified" on the report.
- The key comes from OPENAI_API_KEY in the environment (.env). It is never logged
  or written into the report.

Uses the OpenAI Responses API: POST /v1/responses {model, instructions, input}.
"""
import json
import logging
import os
import re
from datetime import datetime, timezone

import httpx

log = logging.getLogger(__name__)

LABEL = "AI-generated summary - review before sharing."

INSTRUCTIONS = """You write short summaries of voice-AI test calls for an internal NGO tech team.
Write 120-200 words of plain, simple English in 2-3 short paragraphs.
Cover: overall result, the biggest problems, what worked well, and the most useful next step.
RULES:
- Use ONLY facts and numbers that appear in the JSON you are given. Copy numbers exactly.
- Do not calculate new numbers, averages or percentages.
- If something is null or missing, say it was not measured. Do not guess.
- Do not mention any person's name or personal details.
- No headings, no bullet lists, no markdown."""

NUMBER_RE = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")


def build_payload(report: dict, max_transcript_chars: int = 6000) -> dict:
    """The only data the LLM sees: computed metrics + masked transcript."""
    lines, used = [], 0
    for item in report["transcript"]["items"]:
        if item["kind"] != "turn":
            continue
        line = f"{item['time']} {item['role']}: {item['text']}"
        used += len(line)
        if used > max_transcript_chars:
            lines.append("... (transcript cut)")
            break
        lines.append(line)
    acc = {k: v for k, v in report["accuracy"].items() if k != "table"}
    acc["wrong_fields"] = [r["label"] for r in report["accuracy"]["table"] if r["correct"] is False]
    return {
        "call": {k: report["call"][k] for k in ("provider", "model", "language", "audio_mode", "duration_s", "form_completed")},
        "overall": {k: report["summary"][k] for k in ("score", "verdict", "parts", "strengths", "problems")},
        "mishearings": {k: report["mishearings"][k] for k in ("total", "fixed", "unfixed", "number_issues", "wer", "cer")}
        | {"examples": [{"said": i["said"], "heard": i["heard"], "field": i["field_label"], "fixed": i["fixed"]}
                        for i in report["mishearings"]["items"][:5]]},
        "voice_quality": {"ratings": report["voice_quality"]["ratings"], "mos": report["voice_quality"]["mos"].get("mos"),
                          "talk_over": report["voice_quality"]["issues"]["talk_over_count"],
                          "long_silences": len(report["voice_quality"]["issues"]["long_silences"])},
        "latency": {k: report["latency"][k] for k in ("avg_ms", "median_ms", "p90_ms", "max_ms", "rating")},
        "language": {k: report["language"][k] for k in ("selected", "detected_caller_languages",
                                                         "agent_correct_language_pct", "code_mixing_rating")},
        "accuracy": acc,
        "cost": {k: report["cost"][k] for k in ("total_usd", "total_inr", "cost_per_min_usd", "projection_1000_calls_usd")},
        "issues": [{"severity": i["severity"], "title": i["title"], "suggestion": i["suggestion"]} for i in report["issues"]],
        "transcript": lines,
    }


def _allowed_numbers(payload: dict) -> set[float]:
    """Every number in the payload, plus its rounded and percentage forms."""
    allowed: set[float] = {1000.0, 100.0, 5.0, 1.0}  # "per 1,000 calls", "/100", "/5", "1 to 5"
    for match in NUMBER_RE.findall(json.dumps(payload, ensure_ascii=False)):
        value = float(match.replace(",", ""))
        for v in (value, round(value), round(value, 1), round(value, 2)):
            allowed.add(float(v))
        if 0 <= value <= 1:  # ratios are often written as percentages
            allowed.update({float(round(value * 100)), round(value * 100, 1)})
    return allowed


def find_unverified_numbers(text: str, payload: dict) -> list[str]:
    allowed = _allowed_numbers(payload)
    bad = []
    for match in NUMBER_RE.findall(text):
        value = float(match.replace(",", "").rstrip("."))
        if value not in allowed and match not in bad:
            bad.append(match)
    return bad


def _output_text(response_json: dict) -> str:
    """Collect the text parts from a Responses API result."""
    parts = []
    for item in response_json.get("output", []):
        for content in item.get("content", []) or []:
            if content.get("type") == "output_text":
                parts.append(content.get("text", ""))
    return "\n".join(parts).strip()


def generate_summary(report: dict, settings: dict) -> dict:
    cfg = settings["ai_summary"]
    model = os.getenv("SUMMARY_MODEL") or cfg["model"]
    base = {"label": LABEL, "model": model, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if cfg.get("provider") != "openai":
        return {**base, "text": None, "error": f"Provider '{cfg.get('provider')}' is not supported yet."}
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or key == "sk-your-key-here":
        return {**base, "text": None, "error": "OPENAI_API_KEY is not set."}

    payload = build_payload(report)
    try:
        response = httpx.post(
            os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1") + "/responses",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "instructions": INSTRUCTIONS,
                  "input": "Call data (JSON):\n" + json.dumps(payload, ensure_ascii=False)},
            timeout=60,
        )
        response.raise_for_status()
        text = _output_text(response.json())
    except httpx.HTTPStatusError as exc:
        try:
            message = exc.response.json()["error"]["message"]
        except Exception:
            message = exc.response.text[:300]
        log.warning("AI summary failed (%s): %s", exc.response.status_code, message)
        return {**base, "text": None, "error": f"OpenAI error {exc.response.status_code}: {message}"}
    except httpx.HTTPError as exc:
        return {**base, "text": None, "error": f"Network error: {exc}"}

    return {**base, "text": text, "unverified_numbers": find_unverified_numbers(text, payload)}
