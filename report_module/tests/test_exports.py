"""Exports (JSON schema, Markdown, HTML for PDF) and the AI-summary number check."""
import json

import pytest

from report_module.exporters import to_json, to_markdown, validate_report
from report_module.exporters.pdf import to_html
from report_module.report_builder import build_report
from report_module.summary_llm import build_payload, find_unverified_numbers

from .conftest import PROVIDERS, load_sample


@pytest.fixture(scope="module")
def reports():
    return {p: build_report(load_sample(p)) for p in PROVIDERS}


@pytest.mark.parametrize("provider", PROVIDERS)
def test_json_matches_schema(reports, provider):
    report = json.loads(to_json(reports[provider]))
    validate_report(report)  # raises if a field is missing or has the wrong type


@pytest.mark.parametrize("provider", PROVIDERS)
def test_markdown_has_all_sections(reports, provider):
    md = to_markdown(reports[provider])
    for n in range(1, 11):
        assert f"## {n}. " in md
    assert "TEST MODE - dummy data only" in md
    assert "must be reviewed by a team member" in md


@pytest.mark.parametrize("provider", PROVIDERS)
def test_html_for_pdf_renders(reports, provider):
    html = to_html(reports[provider])
    assert html.count("<h2>") == 10
    assert "data:image/png;base64," in html  # charts embedded


def test_indian_scripts_survive_export(reports):
    assert "टेस्ट" in to_markdown(reports["sarvam"])
    assert "சோதனை" in to_html(reports["gemini"])


def test_masked_number_not_in_any_export(reports):
    for text in (to_json(reports["elevenlabs"]), to_markdown(reports["elevenlabs"]), to_html(reports["elevenlabs"])):
        assert "98765" not in text


def test_stage_chart_only_for_split(reports):
    assert to_html(reports["sarvam"]).count("data:image/png") == 3
    assert to_html(reports["gemini"]).count("data:image/png") == 2


# ---------- AI summary number check (no API call) ----------


def test_payload_has_no_tool_internals(reports):
    payload = build_payload(reports["openai"])
    assert "table" not in payload["accuracy"]
    assert payload["transcript"]


def test_unverified_numbers(reports):
    payload = build_payload(reports["openai"])
    avg = payload["latency"]["avg_ms"]
    ok_text = f"Replies averaged {avg} ms and 100% of fields were correct across 1,000 calls."
    assert find_unverified_numbers(ok_text, payload) == []
    bad = find_unverified_numbers("The agent answered 97 questions in 4321 ms.", payload)
    assert "4321" in bad
