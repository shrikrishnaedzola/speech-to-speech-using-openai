"""complete_form: lists missing required fields, including active follow-ups."""
from app.services import tools

FULL_ANSWERS = [
    ("caller_name", "Test Person"),
    ("age", "30"),
    ("district", "Sample District"),
    ("attended_sessions", "yes"),
    ("sessions_attended_count", "3"),
    ("number_of_children", "2"),
    ("children_ages", "5, 8"),
    ("satisfaction_rating", "4"),
    ("consent_to_followup", "no"),
]


def save_all(db, call, form, answers):
    for field_id, value in answers:
        result = tools.save_answer(db, call, form, {"field_id": field_id, "value": value, "confidence": "high"})
        assert result["ok"], result


def test_empty_form_lists_all_required(db, call, form):
    result = tools.complete_form(db, call, form, {})
    missing = [m["field_id"] for m in result["missing_fields"]]
    assert result["ok"] is False
    assert missing == ["caller_name", "age", "district", "attended_sessions",
                       "number_of_children", "satisfaction_rating", "consent_to_followup"]


def test_active_follow_up_is_required(db, call, form):
    # Everything except children_ages, which is required because number_of_children > 0.
    save_all(db, call, form, [a for a in FULL_ANSWERS if a[0] != "children_ages"])
    result = tools.complete_form(db, call, form, {})
    assert [m["field_id"] for m in result["missing_fields"]] == ["children_ages"]


def test_complete_when_all_required_filled(db, call, form):
    save_all(db, call, form, FULL_ANSWERS)
    result = tools.complete_form(db, call, form, {})
    assert result["ok"] is True
    assert call.form_completed is True


def test_optional_fields_not_required(db, call, form):
    # preferred_language and improvement_suggestion are optional.
    save_all(db, call, form, FULL_ANSWERS)
    assert tools.complete_form(db, call, form, {})["ok"] is True


def test_zero_children_no_ages_needed(db, call, form):
    answers = [(f, "0" if f == "number_of_children" else v) for f, v in FULL_ANSWERS if f != "children_ages"]
    save_all(db, call, form, answers)
    assert tools.complete_form(db, call, form, {})["ok"] is True
