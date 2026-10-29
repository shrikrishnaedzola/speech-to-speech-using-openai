"""Mishearings: places where the AI misheard or misunderstood the caller.

Four sources:
1. Expected caller script (if the scenario has one): WER and CER per caller turn.
2. Caller corrections: "No, I said...", "nahi, maine kaha...".
3. Saved value differs from the expected value (or the tester marked it Wrong).
4. Number mix-ups, e.g. "fifteen" saved as 50.

Without an expected script, mishearings that nobody corrected cannot be seen.
"""
import re

from .call_data import CallData
from .text_utils import extract_numbers, normalize_text, value_to_text, values_match

# ---------- WER / CER ----------


def edit_distance(ref: list, hyp: list) -> int:
    """Levenshtein distance (substitutions + deletions + insertions)."""
    previous = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        current = [i]
        for j, h in enumerate(hyp, start=1):
            current.append(min(
                previous[j] + 1,  # deletion
                current[j - 1] + 1,  # insertion
                previous[j - 1] + (r != h),  # substitution
            ))
        previous = current
    return previous[-1]


def wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate = word edits / words in the reference."""
    ref, hyp = normalize_text(reference).split(), normalize_text(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return edit_distance(ref, hyp) / len(ref)


def cer(reference: str, hypothesis: str) -> float:
    """Character Error Rate. Better than WER for Indian scripts, where word splits vary.

    Spaces are removed so "Sample District" vs "SampleDistrict" is not an error.
    Characters are Unicode code points after NFC normalisation, so a Hindi matra
    or Tamil vowel sign counts as one character.
    """
    ref = list(normalize_text(reference).replace(" ", ""))
    hyp = list(normalize_text(hypothesis).replace(" ", ""))
    if not ref:
        return 0.0 if not hyp else 1.0
    return edit_distance(ref, hyp) / len(ref)


def script_error_rates(expected_lines: list[str], caller_turns: list[str]) -> dict:
    """Compare the expected caller script with what was transcribed, line by line (in order).

    Returns per-line rates plus corpus totals (total edits / total reference length).
    """
    pairs = list(zip(expected_lines, caller_turns))
    lines = []
    word_edits = word_total = char_edits = char_total = 0
    for expected, heard in pairs:
        ref_words, hyp_words = normalize_text(expected).split(), normalize_text(heard).split()
        ref_chars = list(normalize_text(expected).replace(" ", ""))
        hyp_chars = list(normalize_text(heard).replace(" ", ""))
        w, c = edit_distance(ref_words, hyp_words), edit_distance(ref_chars, hyp_chars)
        word_edits, word_total = word_edits + w, word_total + len(ref_words)
        char_edits, char_total = char_edits + c, char_total + len(ref_chars)
        lines.append({
            "expected": expected,
            "heard": heard,
            "wer": round(w / len(ref_words), 3) if ref_words else 0.0,
            "cer": round(c / len(ref_chars), 3) if ref_chars else 0.0,
        })
    return {
        "lines": lines,
        "wer": round(word_edits / word_total, 3) if word_total else None,
        "cer": round(char_edits / char_total, 3) if char_total else None,
        "unmatched_lines": abs(len(expected_lines) - len(caller_turns)),
    }


# ---------- caller corrections ----------

CORRECTION_PATTERNS = [
    # English
    r"\bno\b[,.!]?\s*(i|i've|i have)\s+(said|say|told|meant)\b",
    r"\bi\s+(said|meant)\b",
    r"\bthat'?s\s+(not\s+(right|correct|what i said)|wrong)\b",
    r"\bnot\s+\w+[,]?\s+(it'?s|it is|but)\b",
    r"\b(correction|let me correct)\b",
    r"\bactually\b.*\b(it'?s|it is|i am|i'm)\b",
    # Hindi / Hinglish (romanised)
    r"\bnahi[n]?\b[,.!]?\s*(maine|mai|main)\s+(kaha|bola)\b",
    r"\b(maine|mai|main)\s+(kaha|bola)\b",
    r"\bgalat\b",
    r"\b(sahi|theek)\s+nahi\b",
    # Hindi (Devanagari)
    r"मैंने\s+(कहा|बोला)",
    r"गलत",
    r"नहीं[,।]?\s*मैंने",
    # Tamil
    r"நான்\s+சொன்னது",
    r"தவறு",
    r"இல்லை[,.]?\s*நான்",
]
CORRECTION_RE = re.compile("|".join(CORRECTION_PATTERNS), re.IGNORECASE)


def is_correction(text: str) -> bool:
    return bool(CORRECTION_RE.search(text or ""))


# ---------- number mix-ups ----------


def number_confusion(saved, expected) -> str | None:
    """Describe a number mishearing, or None if it does not look like one.

    'teen/ty': 15 <-> 50, 13 <-> 30 ... (very common in English ASR)
    'hindi teen': Hindi "teen" (3) heard as English "-teen"/"thirteen" (13) or vice versa.
    """
    saved_nums, expected_nums = extract_numbers(value_to_text(saved)), extract_numbers(value_to_text(expected))
    if not saved_nums or not expected_nums or saved_nums == expected_nums:
        return None
    for s, e in zip(saved_nums, expected_nums):
        if s == e:
            continue
        pair = {int(s), int(e)}
        for teen in range(13, 20):
            if pair == {teen, (teen - 10) * 10}:
                return f"teen/ty confusion ({int(e)} heard as {int(s)})"
        if pair == {3, 13}:
            return f"Hindi 'teen' (3) vs 'thirteen' ({int(e)} heard as {int(s)})"
        return f"number misheard ({int(e) if e.is_integer() else e} saved as {int(s) if s.is_integer() else s})"
    return "number count differs"


# ---------- main entry ----------


def _save_history(data: CallData) -> dict[str, list[dict]]:
    """Successful save_answer calls per field, in order."""
    history: dict[str, list[dict]] = {}
    for call in data.tool_calls:
        if call.name == "save_answer" and call.success:
            field_id = call.arguments.get("field_id")
            value = call.result.get("value", call.arguments.get("value"))
            history.setdefault(field_id, []).append({"value": value, "ts_ms": call.ts_ms})
    return history


def _nearest_agent_turn_before(data: CallData, index: int) -> str | None:
    for turn in reversed(data.transcript[:index]):
        if turn.role == "agent":
            return turn.text
    return None


def _field_saved_after(data: CallData, ts_ms: float | None) -> str | None:
    """The first field saved after a moment in the call (used to link a correction to a field)."""
    if ts_ms is None:
        return None
    later = [c for c in data.tool_calls if c.name == "save_answer" and c.ts_ms is not None and c.ts_ms >= ts_ms]
    return later[0].arguments.get("field_id") if later else None


def analyze_mishearings(data: CallData) -> dict:
    fields = {f.id: f for f in data.fields}
    history = _save_history(data)
    items: list[dict] = []

    # 1) Values: every saved value that differs from the expected value is a mishearing.
    #    It is "fixed" if the final saved value is correct.
    for field in data.fields:
        expected = field.expected_value
        saves = history.get(field.id, [])
        final_ok = values_match(field.saved_value, expected)
        if field.review_mark == "correct":
            final_ok = True
        elif field.review_mark == "wrong":
            final_ok = False

        if expected is not None and final_ok is not None:
            for save in saves[:-1]:  # earlier values that were replaced
                if values_match(save["value"], expected) is False:
                    items.append(_item(save["ts_ms"], expected, save["value"], field, True, "value", _num(field, save["value"], expected)))
            if final_ok is False and field.saved_value is not None:  # unanswered = "not filled", not a mishearing
                items.append(_item(saves[-1]["ts_ms"] if saves else None, expected, field.saved_value, field,
                                   False, "value", _num(field, field.saved_value, expected)))
        elif len(saves) > 1:
            # No expected value: a changed answer usually means the first one was misheard.
            for save, nxt in zip(saves, saves[1:]):
                if values_match(save["value"], nxt["value"]) is False:
                    items.append(_item(save["ts_ms"], nxt["value"], save["value"], field, True, "changed_value",
                                       _num(field, save["value"], nxt["value"])))
            if field.review_mark == "wrong":
                items.append(_item(saves[-1]["ts_ms"], None, field.saved_value, field, False, "marked_wrong", None))
        elif field.review_mark == "wrong":
            items.append(_item(saves[-1]["ts_ms"] if saves else None, None, field.saved_value, field, False, "marked_wrong", None))

    # 2) Caller corrections. Attach to an existing value item for the same field, or add a new one.
    for index, turn in enumerate(data.transcript):
        if turn.role != "caller" or not is_correction(turn.text):
            continue
        field_id = _field_saved_after(data, turn.ts_ms)
        existing = next((i for i in items if i["field_id"] == field_id and i["fixed"] and not i.get("caller_correction")), None)
        if existing:
            existing["caller_correction"] = turn.text
            existing["transcript_index"] = index
            continue
        items.append({
            "ts_ms": turn.ts_ms,
            "said": turn.text,
            "heard": _nearest_agent_turn_before(data, index),
            "field_id": field_id,
            "field_label": fields[field_id].label if field_id in fields else None,
            "fixed": field_id is not None,
            "source": "caller_correction",
            "number_issue": None,
            "caller_correction": turn.text,
            "transcript_index": index,
        })

    # 3) Expected script (WER/CER)
    script = None
    if data.scenario and data.scenario.caller_script:
        caller_texts = [t.text for t in data.transcript if t.role == "caller"]
        script = script_error_rates(data.scenario.caller_script, caller_texts)

    items.sort(key=lambda i: (i["ts_ms"] is None, i["ts_ms"] or 0))
    fixed = sum(1 for i in items if i["fixed"])
    return {
        "items": items,
        "total": len(items),
        "fixed": fixed,
        "unfixed": len(items) - fixed,
        "number_issues": sum(1 for i in items if i["number_issue"]),
        "wer": script["wer"] if script else None,
        "cer": script["cer"] if script else None,
        "script": script,
        "has_expected_script": script is not None,
        "note": None if script else "No expected caller script for this call: WER/CER not available, "
                                     "and mishearings nobody corrected cannot be detected.",
    }


def _num(field, saved, expected) -> str | None:
    """Only look for number mix-ups in number fields ("do" is also Hindi for 2!)."""
    return number_confusion(saved, expected) if field.type in ("number", "list_number") else None


def _item(ts_ms, said, heard, field, fixed, source, number_issue) -> dict:
    return {
        "ts_ms": ts_ms,
        "said": value_to_text(said) if said is not None else None,
        "heard": value_to_text(heard),
        "field_id": field.id,
        "field_label": field.label,
        "fixed": fixed,
        "source": source,
        "number_issue": number_issue,
    }
