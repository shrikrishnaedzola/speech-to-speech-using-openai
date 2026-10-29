"""Pure form rules: value validation and follow-up conditions.

No database code here, so these functions are easy to unit test.

Field types supported in form JSON:
  text        - any non-empty text
  number      - number, optional "integer", "min", "max"
  choice      - one of "choices" (case-insensitive)
  yes_no      - yes/no, stored as true/false
  list_number - list of numbers, optional "min"/"max" per item and
                "count_field" (list length must equal that field's answer)

A field with "condition" is a follow-up. It is only active when the
condition is true, e.g. {"field": "attended_sessions", "op": "eq", "value": false}.
"""
import re
from typing import Any

YES_WORDS = {"yes", "y", "true", "haan", "haa", "ha", "han", "ji", "ji haan", "1"}
NO_WORDS = {"no", "n", "false", "nahi", "nahin", "na", "0"}

NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


class FieldValueError(ValueError):
    """Raised when an answer is invalid. The message is sent back to the agent."""


def get_field(form: dict, field_id: str) -> dict | None:
    for field in form["fields"]:
        if field["id"] == field_id:
            return field
    return None


# ---------- follow-up conditions ----------

def condition_met(condition: dict, answers: dict[str, Any]) -> bool:
    """True if the condition holds. False if the referenced field has no answer yet."""
    if condition["field"] not in answers:
        return False
    actual = answers[condition["field"]]
    target = condition["value"]
    op = condition.get("op", "eq")
    if op == "eq":
        return actual == target
    if op == "ne":
        return actual != target
    # Numeric comparisons
    try:
        actual, target = float(actual), float(target)
    except (TypeError, ValueError):
        return False
    return {
        "gt": actual > target,
        "gte": actual >= target,
        "lt": actual < target,
        "lte": actual <= target,
    }.get(op, False)


def is_active(field: dict, answers: dict[str, Any]) -> bool:
    """A field without a condition is always active."""
    condition = field.get("condition")
    return condition is None or condition_met(condition, answers)


def active_fields(form: dict, answers: dict[str, Any]) -> list[dict]:
    return [f for f in form["fields"] if is_active(f, answers)]


def missing_required(form: dict, answers: dict[str, Any]) -> list[str]:
    """Ids of active required fields that have no answer yet (in form order)."""
    return [
        f["id"]
        for f in active_fields(form, answers)
        if f.get("required") and f["id"] not in answers
    ]


# ---------- value validation ----------

def _to_number(raw: Any) -> float:
    if isinstance(raw, bool):
        raise FieldValueError("Expected a number.")
    if isinstance(raw, (int, float)):
        return float(raw)
    match = NUMBER_RE.search(str(raw))
    if not match:
        raise FieldValueError("Expected a number, for example 25.")
    return float(match.group())


def _check_range(field: dict, number: float, label: str) -> None:
    low, high = field.get("min"), field.get("max")
    if low is not None and number < low:
        raise FieldValueError(f"{label} must be at least {low}.")
    if high is not None and number > high:
        raise FieldValueError(f"{label} must be at most {high}.")


def _clean_number(number: float) -> int | float:
    return int(number) if number == int(number) else number


def parse_value(field: dict, raw: Any, answers: dict[str, Any] | None = None) -> Any:
    """Validate and convert a raw answer. Raises FieldValueError with a friendly message."""
    answers = answers or {}
    ftype = field["type"]
    label = field.get("label", field["id"])

    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise FieldValueError("The answer is empty.")

    if ftype == "text":
        return str(raw).strip()

    if ftype == "number":
        number = _to_number(raw)
        if field.get("integer") and number != int(number):
            raise FieldValueError(f"{label} must be a whole number.")
        _check_range(field, number, label)
        return _clean_number(number)

    if ftype == "choice":
        text = str(raw).strip().lower()
        for choice in field["choices"]:
            if choice.lower() == text:
                return choice
        raise FieldValueError(f"Answer must be one of: {', '.join(field['choices'])}.")

    if ftype == "yes_no":
        if isinstance(raw, bool):
            return raw
        text = str(raw).strip().lower().rstrip(".!")
        if text in YES_WORDS:
            return True
        if text in NO_WORDS:
            return False
        raise FieldValueError("Answer must be yes or no.")

    if ftype == "list_number":
        if isinstance(raw, list):
            numbers = [_to_number(item) for item in raw]
        else:
            numbers = [float(m) for m in NUMBER_RE.findall(str(raw))]
        if not numbers:
            raise FieldValueError("Expected a list of numbers, for example '4, 7'.")
        for number in numbers:
            _check_range(field, number, "Each value")
        count_field = field.get("count_field")
        if count_field:
            if count_field not in answers:
                raise FieldValueError(f"Ask {count_field} first.")
            expected = int(answers[count_field])
            if len(numbers) != expected:
                raise FieldValueError(
                    f"Got {len(numbers)} values but {count_field} is {expected}. "
                    "Please confirm with the caller."
                )
        return [_clean_number(n) for n in numbers]

    raise FieldValueError(f"Unknown field type '{ftype}'.")


def describe_condition(condition: dict) -> str:
    """Human-readable condition, used in the agent instructions."""
    value = condition["value"]
    if value is True:
        value = "yes"
    elif value is False:
        value = "no"
    symbol = {"eq": "=", "ne": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[condition.get("op", "eq")]
    return f"{condition['field']} {symbol} {value}"
