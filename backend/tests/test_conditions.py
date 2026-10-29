"""Follow-up condition logic: fields appear only when their condition is true."""
from app.services import tools
from app.services.form_logic import active_fields, get_field, is_active


def ids(fields):
    return [f["id"] for f in fields]


def test_follow_ups_hidden_before_parent_answered(form):
    active = ids(active_fields(form, {}))
    assert "reason_not_attended" not in active
    assert "sessions_attended_count" not in active
    assert "children_ages" not in active


def test_attended_yes_shows_count_only(form):
    active = ids(active_fields(form, {"attended_sessions": True}))
    assert "sessions_attended_count" in active
    assert "reason_not_attended" not in active


def test_attended_no_shows_reason_only(form):
    active = ids(active_fields(form, {"attended_sessions": False}))
    assert "reason_not_attended" in active
    assert "sessions_attended_count" not in active


def test_children_ages_only_when_children_gt_zero(form):
    field = get_field(form, "children_ages")
    assert not is_active(field, {"number_of_children": 0})
    assert is_active(field, {"number_of_children": 3})


def test_save_answer_rejects_inactive_follow_up(db, call, form):
    result = tools.save_answer(db, call, form, {"field_id": "reason_not_attended", "value": "busy", "confidence": "high"})
    assert result["ok"] is False
    assert "only asked when" in result["error"]


def test_save_answer_accepts_active_follow_up(db, call, form):
    tools.save_answer(db, call, form, {"field_id": "attended_sessions", "value": "no", "confidence": "high"})
    result = tools.save_answer(db, call, form, {"field_id": "reason_not_attended", "value": "busy", "confidence": "high"})
    assert result["ok"] is True


def test_invalid_answer_returns_error_for_agent(db, call, form):
    result = tools.save_answer(db, call, form, {"field_id": "age", "value": "150", "confidence": "high"})
    assert result["ok"] is False
    assert result["question"] == "How old are you?"


def test_low_confidence_needs_confirmation(db, call, form):
    tools.save_answer(db, call, form, {"field_id": "age", "value": "40", "confidence": "low"})
    from app.services.call_state import answer_rows
    assert answer_rows(db, call.id)["age"].status == "needs_confirmation"


def test_skip_only_optional(db, call, form):
    assert tools.skip_field(db, call, form, {"field_id": "district", "reason": "x"})["ok"] is False
    assert tools.skip_field(db, call, form, {"field_id": "improvement_suggestion", "reason": "x"})["ok"] is True


def test_tool_schemas_are_strict(form):
    for schema in tools.tool_schemas(form, strict=True):
        params = schema["parameters"]
        assert schema["strict"] is True
        assert params["additionalProperties"] is False
        assert set(params["required"]) == set(params["properties"])
