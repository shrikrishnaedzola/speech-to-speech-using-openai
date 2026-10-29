"""Find and mask anything that looks like a phone number or Aadhaar number.

Runs BEFORE any report section is built, so masked text is all that reaches
the report, the exports and the optional AI summary.

Limits: only digit sequences are caught (any script, since Python's \\d matches
Devanagari/Tamil digits too). Numbers spoken as words ("nine eight seven...")
are not detected.
"""
import json
import re

from .call_data import CallData

# 12 digits, optionally in groups of 4: Aadhaar-style. Checked first.
AADHAAR_RE = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")
# 10 digits, optionally +91 / 0 prefix and a separator in the middle: phone-style.
PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?|0)?\d{5}[\s-]?\d{5}(?!\d)")


def _mask(match: re.Match) -> str:
    digits = [c for c in match.group() if c.isdigit()]
    return "X" * (len(digits) - 2) + "".join(digits[-2:])  # keep the last 2 digits only


def mask_text(text: str) -> tuple[str, list[str]]:
    """Return (masked text, list of kinds found)."""
    found = []
    if AADHAAR_RE.search(text):
        found.append("aadhaar")
        text = AADHAAR_RE.sub(_mask, text)
    if PHONE_RE.search(text):
        found.append("phone")
        text = PHONE_RE.sub(_mask, text)
    return text, found


def _mask_any(value, where: str, warnings: list[dict]):
    """Mask strings inside any JSON-like value (str, list, dict)."""
    if isinstance(value, str):
        masked, kinds = mask_text(value)
        for kind in kinds:
            warnings.append({"kind": kind, "where": where})
        return masked
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # A number saved as a field value could itself be a phone number.
        masked, kinds = mask_text(str(int(value)) if float(value).is_integer() else str(value))
        if kinds:
            for kind in kinds:
                warnings.append({"kind": kind, "where": where})
            return masked
        return value
    if isinstance(value, list):
        return [_mask_any(v, where, warnings) for v in value]
    if isinstance(value, dict):
        return {k: _mask_any(v, where, warnings) for k, v in value.items()}
    return value


def mask_call_data(data: CallData) -> tuple[CallData, list[dict]]:
    """Return a masked COPY of the call data plus warnings like {"kind": "phone", "where": "transcript turn 4"}."""
    warnings: list[dict] = []
    raw = json.loads(data.model_dump_json())
    for i, turn in enumerate(raw["transcript"]):
        turn["text"] = _mask_any(turn["text"], f"transcript turn {i + 1} ({turn['role']})", warnings)
    for field in raw["fields"]:
        for key in ("saved_value", "expected_value"):
            field[key] = _mask_any(field[key], f"field {field['id']} ({key})", warnings)
    for i, call in enumerate(raw["tool_calls"]):
        call["arguments"] = _mask_any(call["arguments"], f"tool call {i + 1} arguments", warnings)
        call["result"] = _mask_any(call["result"], f"tool call {i + 1} result", warnings)
    if raw["ratings"].get("notes"):
        raw["ratings"]["notes"] = _mask_any(raw["ratings"]["notes"], "tester notes", warnings)
    if raw.get("scenario"):
        raw["scenario"]["caller_script"] = _mask_any(raw["scenario"]["caller_script"], "scenario script", warnings)
    return CallData.model_validate(raw), warnings
