"""Build the full post-call report (all 10 sections) from CallData.

    report = build_report(call_data, settings)

The result is a plain dict that follows exporters/report.schema.json, so the
React page, Markdown, PDF and the comparison tool all read the same thing.
"""
import re
from datetime import datetime, timezone

from .accuracy import analyze_accuracy
from .call_data import CallData
from .cost import analyze_cost
from .language import analyze_language
from .latency import analyze_latency
from .mishearing import analyze_mishearings
from .pii import mask_call_data
from .scoring import overall_score, part_scores
from .settings import load_settings
from .text_utils import normalize_text
from .voice_quality import analyze_voice_quality

SCHEMA_VERSION = "1.0"
TEST_MODE_BANNER = "TEST MODE - dummy data only"
FOOTER = "AI-assisted test report - must be reviewed by a team member before sharing outside EdZola."
SEVERITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def fmt_ts(ts_ms: float | None) -> str:
    """12345 ms -> '00:12'."""
    if ts_ms is None:
        return "--:--"
    seconds = int(ts_ms // 1000)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


# ---------- Section 2: annotated transcript ----------


def _similar(a: str, b: str) -> float:
    """Word overlap (Jaccard) between two texts, 0..1."""
    wa, wb = set(normalize_text(a).split()), set(normalize_text(b).split())
    return len(wa & wb) / len(wa | wb) if wa and wb else 0.0


def build_transcript(data: CallData, mishearings: dict, language: dict) -> dict:
    turns = data.transcript
    tags: dict[int, set] = {i: set() for i in range(len(turns))}

    # Red: caller corrections and the agent turn that misunderstood.
    for item in mishearings["items"]:
        index = item.get("transcript_index")
        if index is not None:
            tags[index].add("mishearing")
            for j in range(index - 1, -1, -1):
                if turns[j].role == "agent":
                    tags[j].add("mishearing")
                    break

    # Orange: re-asked questions = agent turn right after a failed save, or a question
    # that repeats an earlier question.
    failed_ts = [c.ts_ms for c in data.tool_calls if not c.success and c.ts_ms is not None]
    earlier_questions: list[str] = []
    for i, turn in enumerate(turns):
        if turn.role != "agent":
            continue
        if turn.ts_ms is not None and any(0 <= turn.ts_ms - ts <= 6000 for ts in failed_ts):
            tags[i].add("reask")
        if "?" in turn.text:
            if any(_similar(turn.text, q) >= 0.6 for q in earlier_questions):
                tags[i].add("reask")
            earlier_questions.append(turn.text)

    # Purple: interruptions = caller turn starting near a barge-in event.
    barge_ts = [e.ts_ms for e in data.events if e.type in ("barge_in", "agent_talk_over")]
    for i, turn in enumerate(turns):
        if turn.role == "caller" and turn.ts_ms is not None and any(abs(turn.ts_ms - ts) <= 1500 for ts in barge_ts):
            tags[i].add("interruption")

    for i in language["agent_wrong_language_turn_indexes"]:
        tags[i].add("wrong_language")

    caller_langs = language["caller_turn_languages"]
    items = [
        {
            "kind": "turn",
            "index": i,
            "role": t.role,
            "text": t.text,
            "ts_ms": t.ts_ms,
            "time": fmt_ts(t.ts_ms),
            "detected_language": caller_langs.get(i) if t.role == "caller" else None,
            "tags": sorted(tags[i]),
        }
        for i, t in enumerate(turns)
    ]
    # Blue: tool calls, placed by time between the turns.
    for call in data.tool_calls:
        items.append({
            "kind": "tool",
            "name": call.name,
            "field_id": call.arguments.get("field_id"),
            "value": call.arguments.get("value"),
            "success": call.success,
            "error": call.result.get("error"),
            "ts_ms": call.ts_ms,
            "time": fmt_ts(call.ts_ms),
            "tags": ["tool_call"],
        })
    if all(i["ts_ms"] is not None for i in items):
        items.sort(key=lambda i: (i["ts_ms"], 0 if i["kind"] == "turn" else 1))
    else:
        items = [i for i in items if i["kind"] == "turn"] + [i for i in items if i["kind"] == "tool"]

    return {
        "items": items,
        "legend": {
            "mishearing": "red", "reask": "orange", "tool_call": "blue",
            "interruption": "purple", "wrong_language": "grey",
        },
        "turn_count": len(turns),
    }


# ---------- Section 9: issues and recommendations ----------


def find_issues(data: CallData, s: dict, pii_warnings: list, settings: dict) -> list[dict]:
    issues = []

    def add(severity, section, title, suggestion):
        issues.append({"severity": severity, "section": section, "title": title, "suggestion": suggestion})

    lang = data.call.language
    if pii_warnings:
        add("High", "summary", f"{len(pii_warnings)} number(s) that look like phone/Aadhaar numbers were found and masked.",
            "Use only dummy data. Delete this call's recording and data if real details were used.")

    mis = s["mishearings"]
    if mis["unfixed"]:
        add("High", "mishearings", f"{mis['unfixed']} mishearing(s) were never fixed during the call.",
            "Add a read-back step: the agent repeats each answer and asks the caller to confirm.")
    if mis["number_issues"]:
        add("High" if mis["number_issues"] >= 3 else "Medium", "mishearings",
            f"Agent misheard numbers {mis['number_issues']} time(s) in this {lang} call.",
            f"Add a number confirmation step for {lang} calls (repeat the number back as digits).")
    if mis["cer"] is not None and mis["cer"] > 0.15:
        add("Medium", "mishearings", f"High transcription error rate (CER {mis['cer']:.0%}).",
            "Try another model or audio mode, and check microphone quality.")

    lat = s["latency"]
    if lat["avg_ms"] is not None and lat["avg_ms"] > lat["thresholds"]["ok"]:
        tool_related = any("tool call" in x["context"] for x in lat["slowest"])
        add("High", "latency", f"Slow replies: average {lat['avg_ms']} ms (Poor > {lat['thresholds']['ok']} ms).",
            "Slowest turns follow tool calls: let the agent ask the next question while the answer is saved."
            if tool_related else "Shorten instructions and replies, or test a faster model.")
    elif lat["avg_ms"] is not None and lat["avg_ms"] > lat["thresholds"]["good"]:
        add("Medium", "latency", f"Replies are OK but not fast: average {lat['avg_ms']} ms.",
            "Check the slowest turns below for tool calls or long replies.")

    acc = s["accuracy"]
    if acc["completion"] is not None and acc["completion"] < 1:
        missing = acc["required_total"] - acc["required_filled"]
        add("High", "accuracy", f"{missing} required field(s) were not filled.",
            "Make sure the agent calls complete_form and asks the missing questions it returns.")
    if acc["field_accuracy"] is not None and acc["field_accuracy"] < 0.8:
        add("High", "accuracy", f"Only {acc['field_accuracy']:.0%} of filled fields are correct.",
            "Review the wrong fields below; add confirmation for those question types.")
    if acc["filled_fields"] and acc["checked_fields"] == 0:
        add("Medium", "accuracy", "No field was marked Correct/Wrong, so accuracy is unknown.",
            "Mark every filled field in the tester (Column 2), then click Regenerate report.")
    elif acc["checked_fields"] < acc["filled_fields"]:
        add("Low", "accuracy", f"{acc['filled_fields'] - acc['checked_fields']} filled field(s) have no Correct/Wrong mark.",
            "Mark every filled field in the tester, then regenerate this report.")
    if acc["follow_up_errors"]:
        add("Medium", "accuracy", f"{acc['follow_up_errors']} follow-up question(s) were asked when not needed, or missed.",
            "Make the follow-up rules clearer in the agent instructions.")
    if acc["tool_success_rate"] is not None and acc["tool_success_rate"] < 0.8:
        add("Medium", "accuracy", f"Only {acc['tool_success_rate']:.0%} of tool calls succeeded.",
            "Check the validation errors: the agent may be sending values in the wrong format.")
    if acc["invalid_answers"] > acc["invalid_answers_recovered"]:
        add("Medium", "accuracy",
            f"{acc['invalid_answers'] - acc['invalid_answers_recovered']} rejected answer(s) were never re-asked successfully.",
            "Tell the agent to always re-ask after an 'ok: false' tool result.")

    lng = s["language"]
    pct = lng["agent_correct_language_pct"]
    if pct is not None and pct < 0.9:
        add("High", "language", f"Agent replied in the wrong language in {1 - pct:.0%} of turns.",
            f"State the language more firmly in the instructions, e.g. 'Always reply in {lang}'.")
    if lng["code_mixing_rating"] is not None and lng["code_mixing_rating"] <= 2:
        add("Medium", "language", "Tester rated code-mixing handling low.",
            "Allow the agent to reply in the caller's mix (e.g. Hinglish) in the instructions.")

    vq = s["voice_quality"]
    low = [k for k, v in vq["ratings"].items() if v is not None and v <= 2]
    if low:
        add("Medium", "voice_quality", f"Low tester rating for: {', '.join(k.replace('_', ' ') for k in low)}.",
            "Try a different voice for this language.")
    issues_vq = vq["issues"]
    if issues_vq["talk_over_count"] > 5:
        add("Medium", "voice_quality", f"{issues_vq['talk_over_count']} interruptions / talk-overs.",
            "Use a headset (echo counts as interruptions) and check turn-detection settings.")
    if issues_vq["long_silences"]:
        add("Medium" if len(issues_vq["long_silences"]) > 2 else "Low", "voice_quality",
            f"{len(issues_vq['long_silences'])} long silence(s) over {settings['long_silence_ms']} ms.",
            "See the slowest turns in the Latency section.")
    if issues_vq["cut_off_sentences"]:
        add("Low", "voice_quality", f"{len(issues_vq['cut_off_sentences'])} agent sentence(s) were cut off.",
            "Usually caused by interruptions; check turn detection sensitivity.")
    if issues_vq["repeated_phrases"]:
        add("Low", "voice_quality", f"{len(issues_vq['repeated_phrases'])} phrase(s) repeated by the agent.",
            "Ask the agent to vary acknowledgements in the instructions.")

    cost = s["cost"]
    if cost["total_usd"] is None:
        add("Low", "cost", "Cost could not be calculated (rates not set).",
            "Fill in the rates for this provider in report_module/settings.json.")

    issues.sort(key=lambda i: SEVERITY_ORDER[i["severity"]])
    return issues


# ---------- Section 1: strengths and problems ----------

STRENGTH_TEXT = {
    "accuracy": lambda s: f"Form data was accurate: {_pct(s['accuracy']['field_accuracy'])} of filled fields correct, "
                          f"{_pct(s['accuracy']['completion'])} of required fields filled.",
    "mishearings": lambda s: "Few understanding errors: "
                             + (f"{s['mishearings']['total']} mishearing(s), {s['mishearings']['fixed']} fixed."
                                if s['mishearings']['total'] else "no mishearings found")
                             + ("" if s['mishearings']['has_expected_script'] or s['accuracy']['checked_fields']
                                else " (no expected answers, so only caller corrections were checked)."),
    "latency": lambda s: f"Fast replies: average {s['latency']['avg_ms']} ms.",
    "voice_quality": lambda s: f"Voice rated well by the tester (average {s['voice_quality']['ratings_avg']}/5).",
    "language": lambda s: f"Replied in {s['language']['selected']} in "
                          f"{_pct(s['language']['agent_correct_language_pct'])} of turns.",
    "cost": lambda s: f"Low cost: ${s['cost']['cost_per_min_usd']} per minute.",
}


def _pct(value) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def strengths_and_problems(parts: dict, sections: dict, issues: list) -> tuple[list[str], list[str]]:
    # A section with a High/Medium issue is never listed as a strength.
    flagged = {i["section"] for i in issues if i["severity"] in ("High", "Medium")}
    good = sorted([(v, k) for k, v in parts.items() if v is not None and v >= 75 and k not in flagged], reverse=True)
    strengths = [STRENGTH_TEXT[k](sections) for _, k in good[:3]]
    extras = []
    if sections["accuracy"]["tool_success_rate"] == 1.0:
        extras.append("Every tool call succeeded.")
    if sections["accuracy"]["follow_ups"] and sections["accuracy"]["follow_up_errors"] == 0:
        extras.append("Follow-up questions were asked only when needed.")
    if sections["accuracy"]["form_completed"]:
        extras.append("The form was completed in the call.")
    strengths += extras[: 3 - len(strengths)]
    problems = [i["title"] for i in issues[:3]]
    return strengths, problems


# ---------- main ----------


def file_name_base(call: dict) -> str:
    """report_{provider}_{model}_{language}_{date}_{call_id} with safe characters only."""
    date = (call.get("started_at") or "")[:10] or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parts = [call["provider"], call["model"], call["language"], date, str(call["call_id"])]
    return "report_" + "_".join(re.sub(r"[^A-Za-z0-9.-]+", "-", p).strip("-") for p in parts)


def build_report(call_data: CallData, settings: dict | None = None, with_ai_summary: bool | None = None) -> dict:
    settings = settings or load_settings()

    # Mask phone/Aadhaar-like numbers FIRST, so nothing below sees them.
    data, pii_warnings = mask_call_data(call_data)

    sections = {}
    sections["mishearings"] = analyze_mishearings(data)
    sections["latency"] = analyze_latency(data, settings)
    sections["accuracy"] = analyze_accuracy(data)
    sections["cost"] = analyze_cost(data, settings)
    sections["language"] = analyze_language(data, sections["mishearings"])
    sections["voice_quality"] = analyze_voice_quality(data, settings)

    parts = part_scores(sections, settings)
    score = overall_score(parts, settings["score_weights"])
    issues = find_issues(data, sections, pii_warnings, settings)
    strengths, problems = strengths_and_problems(parts, sections, issues)
    # A call with a High-severity problem cannot be "Good", whatever the score.
    if score["verdict"] == "Good" and any(i["severity"] == "High" for i in issues):
        score["verdict"] = "Needs improvement"
        score["verdict_note"] = "Capped: the call has at least one High-severity issue."

    call = data.call.model_dump()
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "test_mode": True,
        "banner": TEST_MODE_BANNER,
        "footer": FOOTER,
        "file_name_base": file_name_base(call),
        "call": call,
        "summary": {**score, "strengths": strengths, "problems": problems},
        "transcript": build_transcript(data, sections["mishearings"], sections["language"]),
        **sections,
        "issues": issues,
        "pii": {"found": bool(pii_warnings), "warnings": pii_warnings},
        "ai_summary": None,
    }

    # AI summary: when asked for explicitly, or on every report if auto_on_generate is true.
    run_summary = with_ai_summary if with_ai_summary is not None else settings["ai_summary"]["auto_on_generate"]
    if run_summary:
        from .summary_llm import generate_summary  # imported here: optional feature
        report["ai_summary"] = generate_summary(report, settings)
    return report
