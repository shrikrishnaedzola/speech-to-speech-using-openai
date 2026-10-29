"""Latency stats, accuracy, cost per provider, overall score, PII masking, language."""
import pytest

from report_module.accuracy import analyze_accuracy
from report_module.cost import analyze_cost
from report_module.language import detect_language
from report_module.latency import analyze_latency, median, percentile, rate_latency
from report_module.pii import mask_call_data, mask_text
from report_module.report_builder import build_report
from report_module.scoring import overall_score, verdict

from .conftest import PROVIDERS, load_sample, minimal_call

# ---------- latency ----------


def test_percentile_and_median():
    values = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    assert percentile(values, 90) == 900
    assert percentile(values, 100) == 1000
    assert median(values) == 550
    assert median([3, 1, 2]) == 2
    assert percentile([], 90) is None


def test_latency_rating(settings):
    th = settings["latency_thresholds_ms"]
    assert rate_latency(800, th) == "Good"
    assert rate_latency(1200, th) == "OK"
    assert rate_latency(1600, th) == "Poor"


def test_latency_section(settings):
    data = minimal_call(turn_metrics=[{"turn": i + 1, "latency_ms": ms} for i, ms in enumerate([500, 900, 1300, 2500])])
    result = analyze_latency(data, settings)
    assert result["avg_ms"] == 1300 and result["median_ms"] == 1100
    assert result["p90_ms"] == 2500 and result["max_ms"] == 2500
    assert [s["latency_ms"] for s in result["slowest"]] == [2500, 1300, 900]
    assert result["has_stage_split"] is False


def test_sarvam_stage_split(settings):
    result = analyze_latency(load_sample("sarvam"), settings)
    assert result["has_stage_split"]
    assert "slowest stage" in result["slowest"][0]["context"]


# ---------- accuracy ----------


def test_accuracy_and_completion():
    result = analyze_accuracy(load_sample("sarvam"))
    assert result["filled_fields"] == 8
    assert result["correct_fields"] == 7
    assert result["field_accuracy"] == pytest.approx(7 / 8, abs=0.001)
    assert result["required_filled"] == 8 and result["required_total"] == 9  # children_ages missing
    assert result["invalid_answers"] == 1 and result["invalid_answers_recovered"] == 0


def test_follow_up_correctness():
    result = analyze_accuracy(load_sample("openai"))
    by_id = {f["field_id"]: f for f in result["follow_ups"]}
    assert by_id["sessions_attended_count"]["needed"] and by_id["sessions_attended_count"]["asked"]
    assert not by_id["reason_not_attended"]["needed"] and not by_id["reason_not_attended"]["asked"]
    assert result["follow_up_errors"] == 0


def test_follow_up_asked_when_not_needed():
    data = minimal_call(
        fields=[{"id": "reason", "label": "Reason", "condition": "attended = no", "active": False}],
        tool_calls=[{"name": "save_answer", "arguments": {"field_id": "reason"}, "success": False,
                     "result": {"error": "only asked when attended = no"}}],
    )
    assert analyze_accuracy(data)["follow_up_errors"] == 1


def test_unreviewed_fields_use_expected_value():
    data = minimal_call(fields=[
        {"id": "age", "label": "Age", "status": "filled", "saved_value": 35, "expected_value": "35"},
        {"id": "district", "label": "District", "status": "filled", "saved_value": "X", "expected_value": "Y"},
    ])
    result = analyze_accuracy(data)
    assert result["correct_fields"] == 1 and result["field_accuracy"] == 0.5


# ---------- cost ----------


def test_cost_openai(settings):
    data = minimal_call(usage={"voice_seconds": 120})
    result = analyze_cost(data, settings)
    assert result["total_usd"] == pytest.approx(0.10)  # 2 min x $0.05
    assert result["total_inr"] == pytest.approx(0.10 * settings["currency"]["inr_per_usd"])
    assert result["projection_1000_calls_usd"] == pytest.approx(100.0)
    assert result["cost_per_min_usd"] == pytest.approx(0.05)


def test_cost_falls_back_to_duration(settings):
    result = analyze_cost(minimal_call(), settings)  # no usage reported, duration 120 s
    assert result["voice_seconds_basis"] == "call duration"
    assert result["total_usd"] == pytest.approx(0.10)


@pytest.mark.parametrize("provider", ["sarvam", "gemini", "elevenlabs"])
def test_cost_unset_rates_warn_not_crash(provider, settings):
    result = analyze_cost(load_sample(provider), settings)
    assert result["total_usd"] is None
    assert any("No rate set" in w for w in result["warnings"])


def test_cost_with_custom_rates(settings):
    settings["cost"]["providers"]["sarvam"]["default"][0]["usd"] = 1.0  # $1 per STT hour
    data = load_sample("sarvam")
    result = analyze_cost(data, settings)
    assert result["total_usd"] == pytest.approx(data.usage.stt_seconds / 3600)


# ---------- overall score ----------


def test_overall_score_weighted():
    parts = {"accuracy": 100, "mishearings": 100, "latency": 0, "voice_quality": 100, "language": 100, "cost": 100}
    weights = {"accuracy": 35, "mishearings": 15, "latency": 20, "voice_quality": 15, "language": 10, "cost": 5}
    assert overall_score(parts, weights)["score"] == 80


def test_missing_parts_reweighted():
    parts = {"accuracy": 100, "mishearings": None, "latency": 50, "voice_quality": None, "language": None, "cost": None}
    weights = {"accuracy": 35, "mishearings": 15, "latency": 20, "voice_quality": 15, "language": 10, "cost": 5}
    result = overall_score(parts, weights)
    assert result["score"] == round((100 * 35 + 50 * 20) / 55)
    assert set(result["missing_parts"]) == {"mishearings", "voice_quality", "language", "cost"}


def test_verdicts():
    assert verdict(80) == "Good" and verdict(60) == "Needs improvement" and verdict(30) == "Poor"


def test_high_issue_caps_verdict():
    report = build_report(load_sample("openai"))  # slow replies = High issue
    assert report["summary"]["verdict"] == "Needs improvement"


# ---------- PII ----------


@pytest.mark.parametrize("text, kind", [
    ("call me on 9876543210", "phone"),
    ("+91 98765 43210", "phone"),
    ("my number is 98765-43210", "phone"),
    ("aadhaar 1234 5678 9012", "aadhaar"),
    ("१२३४५६७८९०", "phone"),  # Devanagari digits
])
def test_pii_masked(text, kind):
    masked, kinds = mask_text(text)
    assert kind in kinds
    assert sum(c.isdigit() for c in masked) == 2  # only the last 2 digits remain


@pytest.mark.parametrize("text", ["I am 35", "two children aged 6 and 9", "rating 4 of 5", "year 2026"])
def test_normal_numbers_not_masked(text):
    assert mask_text(text) == (text, [])


def test_pii_masked_everywhere_in_report():
    report = build_report(load_sample("elevenlabs"))
    assert report["pii"]["found"]
    text = str(report)
    assert "98765" not in text and "43210" not in text
    assert any(i["severity"] == "High" and "masked" in i["title"] for i in report["issues"])


def test_mask_call_data_copies():
    data = minimal_call(transcript=[{"role": "caller", "text": "9876543210"}])
    masked, warnings = mask_call_data(data)
    assert data.transcript[0].text == "9876543210"  # original untouched
    assert masked.transcript[0].text == "XXXXXXXX10" and warnings


# ---------- language ----------


@pytest.mark.parametrize("text, language", [
    ("I have two children", "English"),
    ("मेरे तीन बच्चे हैं", "Hindi"),
    ("எனக்கு இரண்டு குழந்தைகள்", "Tamil"),
    ("నాకు ఇద్దరు పిల్లలు", "Telugu"),
    ("ನನಗೆ ಇಬ್ಬರು ಮಕ್ಕಳು", "Kannada"),
    ("আমার দুটি সন্তান", "Bengali"),
    ("Kaam tha, time nahi mila", "Hindi"),
])
def test_detect_language(text, language):
    assert detect_language(text, "Hindi")["language"] == language


def test_marathi_uses_selected_language():
    assert detect_language("माझे नाव टेस्ट आहे", "Marathi")["language"] == "Marathi"


def test_hinglish_is_code_mixed():
    assert detect_language("Kaam tha, time nahi mila", "Hindi")["code_mixed"]


def test_wrong_language_reply_found():
    report = build_report(load_sample("gemini"))
    assert report["language"]["agent_wrong_language_turn_indexes"]
    assert report["language"]["agent_correct_language_pct"] < 1


# ---------- all providers ----------


@pytest.mark.parametrize("provider", PROVIDERS)
def test_every_sample_builds_a_full_report(provider):
    report = build_report(load_sample(provider))
    for key in ("summary", "transcript", "mishearings", "voice_quality", "latency", "language",
                "accuracy", "cost", "issues"):
        assert key in report
    assert report["summary"]["score"] is not None
    assert report["file_name_base"].startswith(f"report_{provider}_")
    assert report["banner"] == "TEST MODE - dummy data only"


def test_accuracy_unknown_when_nothing_checked():
    data = minimal_call(fields=[{"id": "age", "label": "Age", "status": "filled", "saved_value": 35}])
    result = analyze_accuracy(data)
    assert result["field_accuracy"] is None and result["checked_fields"] == 0


# ---------- OpenAI tester adapter ----------


def test_adapter_mixes_naive_and_aware_times():
    from report_module.adapters.openai_tester import to_call_data

    tester_report = {
        "call": {"id": 7, "mode": "live", "model": "gpt-live-1", "voice": "marin", "language": "English",
                 "started_at": "2026-10-26T10:00:00", "duration_s": 60, "form_completed": False},  # naive (SQLite)
        "form": {"name": "Test form"},
        "fields": [],
        "metrics": {"turn_latencies_ms": [{"turn": 1, "latency_ms": 900}], "usage_seconds": 61, "interruptions": 0},
        "tool_calls": [{"name": "save_answer", "arguments": {"field_id": "age"}, "success": True, "result": {},
                        "duration_ms": 5, "created_at": "2026-10-26T10:00:05"}],
        "transcript": [{"role": "caller", "text": "Hello", "ts": "2026-10-26T10:00:02.000Z"}],  # aware
    }
    data = to_call_data(tester_report, extras={"turn_ts_ms": {1: 3000}})
    assert data.transcript[0].ts_ms == 2000
    assert data.tool_calls[0].ts_ms == 5000
    assert data.turn_metrics[0].ts_ms == 3000
    assert data.usage.voice_seconds == 61
