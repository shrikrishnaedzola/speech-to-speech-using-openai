"""Formatting helpers shared by the Markdown and PDF templates (Jinja2 filters)."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"

SECTION_TITLES = {
    "summary": "1. Call summary", "transcript": "2. Transcript", "mishearings": "3. Mishearings",
    "voice_quality": "4. Voice quality", "latency": "5. Latency", "language": "6. Language support",
    "accuracy": "7. Accuracy (form data)", "cost": "8. Cost", "issues": "9. Issues and recommendations",
    "ai_summary": "10. AI-written summary",
}
PART_LABELS = {
    "accuracy": "Accuracy", "mishearings": "Mishearings", "latency": "Latency",
    "voice_quality": "Voice quality", "language": "Language support", "cost": "Cost",
}
TAG_LABELS = {
    "mishearing": "Mishearing", "reask": "Re-asked", "tool_call": "Tool call",
    "interruption": "Interruption", "wrong_language": "Wrong language",
}
SOURCE_LABELS = {
    "value": "Saved value differs from expected", "changed_value": "Answer changed later",
    "marked_wrong": "Tester marked wrong", "caller_correction": "Caller corrected the agent",
}


def pct(value) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def ms(value) -> str:
    return "n/a" if value is None else f"{value:,.0f} ms"


def usd(value) -> str:
    if value is None:
        return "n/a"
    return f"${value:,.4f}" if value < 1 else f"${value:,.2f}"


def inr(value) -> str:
    return "n/a" if value is None else f"₹{value:,.2f}"


def na(value) -> str:
    return "n/a" if value is None or value == "" else str(value)


def yes_no(value) -> str:
    return {True: "Yes", False: "No"}.get(value, "n/a")


def duration(seconds) -> str:
    if not seconds:
        return "n/a"
    return f"{int(seconds // 60)} min {int(seconds % 60)} s"


def md_cell(value) -> str:
    """Make text safe inside a Markdown table cell."""
    return na(value).replace("|", "\\|").replace("\n", " ")


def make_env(autoescape: bool) -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]) if autoescape else False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters.update(pct=pct, ms=ms, usd=usd, inr=inr, na=na, yes_no=yes_no, duration=duration, md=md_cell)
    env.globals.update(SECTION_TITLES=SECTION_TITLES, PART_LABELS=PART_LABELS, TAG_LABELS=TAG_LABELS,
                       SOURCE_LABELS=SOURCE_LABELS)
    return env
