"""Field validation: types, ranges and choices."""
import pytest

from app.services.form_logic import FieldValueError, get_field, parse_value


def test_text_is_trimmed(form):
    assert parse_value(get_field(form, "district"), "  Sample District ") == "Sample District"


def test_empty_answer_rejected(form):
    with pytest.raises(FieldValueError):
        parse_value(get_field(form, "caller_name"), "   ")


@pytest.mark.parametrize("raw, expected", [("34", 34), ("I am 45 years", 45), (60, 60), ("18", 18), ("100", 100)])
def test_age_valid(form, raw, expected):
    assert parse_value(get_field(form, "age"), raw) == expected


@pytest.mark.parametrize("raw", ["17", "150", "abc", "34.5"])
def test_age_invalid(form, raw):
    with pytest.raises(FieldValueError):
        parse_value(get_field(form, "age"), raw)


def test_rating_range(form):
    field = get_field(form, "satisfaction_rating")
    assert parse_value(field, "5") == 5
    with pytest.raises(FieldValueError, match="at most 5"):
        parse_value(field, "6")
    with pytest.raises(FieldValueError, match="at least 1"):
        parse_value(field, "0")


def test_choice_case_insensitive(form):
    assert parse_value(get_field(form, "preferred_language"), "hindi") == "Hindi"


def test_choice_invalid(form):
    with pytest.raises(FieldValueError, match="one of"):
        parse_value(get_field(form, "preferred_language"), "French")


@pytest.mark.parametrize("raw, expected", [("yes", True), ("Haan", True), ("no", False), ("nahi", False), (True, True)])
def test_yes_no(form, raw, expected):
    assert parse_value(get_field(form, "attended_sessions"), raw) is expected


def test_yes_no_invalid(form):
    with pytest.raises(FieldValueError):
        parse_value(get_field(form, "attended_sessions"), "maybe")


def test_children_ages_must_match_count(form):
    field = get_field(form, "children_ages")
    assert parse_value(field, "4, 7", {"number_of_children": 2}) == [4, 7]
    assert parse_value(field, [4, 7], {"number_of_children": 2}) == [4, 7]
    with pytest.raises(FieldValueError, match="Got 1 values"):
        parse_value(field, "4", {"number_of_children": 2})


def test_children_ages_need_count_first(form):
    with pytest.raises(FieldValueError, match="number_of_children first"):
        parse_value(get_field(form, "children_ages"), "4", {})
