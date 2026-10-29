"""WER/CER (English, Hindi, Tamil), correction detection, number mishearings."""
import pytest

from report_module.mishearing import analyze_mishearings, cer, is_correction, number_confusion, script_error_rates, wer
from report_module.text_utils import extract_numbers, values_match

from .conftest import load_sample, minimal_call

# ---------- WER / CER ----------


def test_wer_english():
    assert wer("I attended fifteen sessions", "I attended fifteen sessions") == 0
    assert wer("I attended fifteen sessions", "I attended fifty sessions") == pytest.approx(1 / 4)
    assert wer("yes", "") == 1.0


def test_wer_ignores_case_and_punctuation():
    assert wer("Yes, I did.", "yes i did") == 0


def test_cer_english():
    assert cer("fifteen", "fifty") == pytest.approx(3 / 7)  # f-i-f-t-e-e-n vs f-i-f-t-y: 1 sub + 2 del


def test_wer_cer_hindi():
    ref, hyp = "मेरे तीन बच्चे हैं", "मेरे तेरह बच्चे हैं"
    assert wer(ref, hyp) == pytest.approx(1 / 4)
    # CER is lower than WER: only part of one word is wrong
    assert 0 < cer(ref, hyp) < wer(ref, hyp)


def test_cer_hindi_matra_counts_as_character():
    # "है" vs "हैं": only the anusvara differs -> 1 edit
    assert cer("है", "हैं") == pytest.approx(1 / 2)


def test_wer_cer_tamil():
    ref, hyp = "எனக்கு இரண்டு குழந்தைகள்", "எனக்கு இருண்டு குழந்தைகள்"
    assert wer(ref, hyp) == pytest.approx(1 / 3)
    assert cer(ref, hyp) < 0.1


def test_cer_ignores_spaces():
    assert cer("Sample District", "SampleDistrict") == 0


def test_script_error_rates_corpus():
    result = script_error_rates(["one two three", "four five"], ["one two three", "four six"])
    assert result["wer"] == pytest.approx(1 / 5)
    assert result["lines"][1]["wer"] == pytest.approx(1 / 2)


# ---------- corrections ----------


@pytest.mark.parametrize("text", [
    "No, I said fifteen, not fifty.",
    "That's not right, it is 35",
    "Actually it's Sample District",
    "nahi, maine kaha teen",
    "Galat hai",
    "नहीं, मैंने कहा तीन",
    "நான் சொன்னது இரண்டு",
])
def test_corrections_detected(text):
    assert is_correction(text)


@pytest.mark.parametrize("text", ["Yes, go ahead.", "No.", "I have two children", "नहीं आ पाया"])
def test_normal_answers_not_corrections(text):
    assert not is_correction(text)


# ---------- numbers ----------


def test_extract_numbers():
    assert extract_numbers("I am thirty five") == [35]
    assert extract_numbers("Six and nine") == [6, 9]
    assert extract_numbers("teen bachche") == [3]
    assert extract_numbers("मेरी उम्र ४५ है") == [45]  # Devanagari digits


@pytest.mark.parametrize("saved, expected, phrase", [
    (50, 15, "teen/ty"),
    (13, 3, "Hindi 'teen'"),
    (40, 41, "number misheard"),
])
def test_number_confusion(saved, expected, phrase):
    assert phrase in number_confusion(saved, expected)


def test_number_confusion_none_when_equal():
    assert number_confusion(15, "fifteen") is None


def test_values_match():
    assert values_match(True, "haan")
    assert values_match([6, 9], "6, 9")
    assert values_match(35, "thirty five")
    assert values_match("Sample District", "sample district.")
    assert values_match(50, "15") is False
    assert values_match(50, None) is None


# ---------- whole-call analysis ----------


def test_fixed_number_mishearing_with_correction():
    result = analyze_mishearings(load_sample("openai"))
    assert result["total"] == 1 and result["fixed"] == 1
    item = result["items"][0]
    assert item["said"] == "15" and item["heard"] == "50"
    assert "teen/ty" in item["number_issue"]
    assert item["caller_correction"].startswith("No, I said")


def test_unfixed_mishearing():
    result = analyze_mishearings(load_sample("sarvam"))
    assert result["unfixed"] == 1
    assert result["items"][0]["field_id"] == "number_of_children"
    assert result["wer"] > 0 and result["cer"] > 0


def test_changed_value_without_expected_counts_as_fixed():
    data = minimal_call(
        fields=[{"id": "age", "label": "Age", "type": "number", "saved_value": 15, "status": "filled"}],
        tool_calls=[
            {"name": "save_answer", "arguments": {"field_id": "age", "value": "50"}, "success": True, "result": {"value": 50}},
            {"name": "save_answer", "arguments": {"field_id": "age", "value": "15"}, "success": True, "result": {"value": 15}},
        ],
    )
    result = analyze_mishearings(data)
    assert result["total"] == 1 and result["fixed"] == 1
    assert result["items"][0]["source"] == "changed_value"


def test_no_script_means_no_wer():
    result = analyze_mishearings(load_sample("gemini"))
    assert result["wer"] is None and result["note"]
