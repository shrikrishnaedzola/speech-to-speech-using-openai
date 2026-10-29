"""Accuracy of the saved form data, follow-ups, error recovery and tool calls."""
from .call_data import CallData
from .text_utils import value_to_text, values_match

VALUE_STATUSES = {"filled", "needs_confirmation"}


def _is_correct(field) -> bool | None:
    """Tester mark wins; otherwise compare with the expected value; None = unknown."""
    if field.review_mark:
        return field.review_mark == "correct"
    return values_match(field.saved_value, field.expected_value)


def analyze_accuracy(data: CallData) -> dict:
    active = [f for f in data.fields if f.active]
    filled = [f for f in active if f.status in VALUE_STATUSES and f.saved_value is not None]
    checked = {f.id: _is_correct(f) for f in filled}
    correct = [fid for fid, ok in checked.items() if ok]
    required = [f for f in active if f.required]
    required_filled = [f for f in required if f in filled]

    # ----- follow-up correctness -----
    attempted = {c.arguments.get("field_id") for c in data.tool_calls if c.name == "save_answer"}
    follow_ups = []
    for f in data.fields:
        if not f.condition:
            continue
        asked = f.id in attempted or f.status != "pending"
        follow_ups.append({
            "field_id": f.id,
            "label": f.label,
            "condition": f.condition,
            "needed": f.active,
            "asked": asked,
            "correct": asked == f.active,
        })

    # ----- error recovery -----
    saves = [c for c in data.tool_calls if c.name == "save_answer"]
    invalid = [c for c in saves if not c.success]
    recovered = 0
    for bad in invalid:
        field_id = bad.arguments.get("field_id")
        later_ok = any(
            c.success and c.arguments.get("field_id") == field_id and (c.ts_ms or 0) >= (bad.ts_ms or 0)
            for c in saves if c is not bad
        )
        recovered += later_ok
    success_counts: dict[str, int] = {}
    for c in saves:
        if c.success:
            success_counts[c.arguments.get("field_id")] = success_counts.get(c.arguments.get("field_id"), 0) + 1
    corrections_saved = sum(1 for n in success_counts.values() if n > 1)

    total_tools = len(data.tool_calls)
    failed_tools = [c for c in data.tool_calls if not c.success]
    validation_errors = [
        {"name": c.name, "field_id": c.arguments.get("field_id"), "error": c.result.get("error")}
        for c in failed_tools if c.result.get("error")
    ]

    # ----- table -----
    table = []
    for f in data.fields:
        if not f.active and f.status == "pending":
            continue  # follow-up correctly not asked: leave out of the table
        ok = checked.get(f.id)
        notes = []
        if f.status == "needs_confirmation":
            notes.append("needs confirmation")
        if f.status == "skipped":
            notes.append("skipped")
        if f.required and f.status == "pending":
            notes.append("required but not filled")
        if success_counts.get(f.id, 0) > 1:
            notes.append(f"saved {success_counts[f.id]} times")
        table.append({
            "field_id": f.id,
            "label": f.label,
            "expected": value_to_text(f.expected_value) if f.expected_value is not None else None,
            "saved": value_to_text(f.saved_value) if f.saved_value is not None else None,
            "correct": ok,
            "notes": ", ".join(notes),
        })

    return {
        "filled_fields": len(filled),
        "checked_fields": sum(1 for v in checked.values() if v is not None),
        "correct_fields": len(correct),
        # Field accuracy = correct / filled (unchecked fields count as not correct, as in the tester).
        # If NO field was checked at all, accuracy is unknown (None), not 0%.
        "field_accuracy": round(len(correct) / len(filled), 3) if filled and any(v is not None for v in checked.values()) else None,
        "required_total": len(required),
        "required_filled": len(required_filled),
        "completion": round(len(required_filled) / len(required), 3) if required else None,
        "form_completed": data.call.form_completed,
        "follow_ups": follow_ups,
        "follow_up_errors": sum(1 for f in follow_ups if not f["correct"]),
        "invalid_answers": len(invalid),
        "invalid_answers_recovered": recovered,
        "corrections_saved": corrections_saved,
        "tool_calls_total": total_tools,
        "tool_calls_failed": len(failed_tools),
        "tool_success_rate": round((total_tools - len(failed_tools)) / total_tools, 3) if total_tools else None,
        "validation_errors": validation_errors,
        "table": table,
    }
