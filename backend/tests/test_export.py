"""Export: JSON and CSV reports, plus accuracy/completion scores."""
import csv
import io
import json

from app.models import Review
from app.services import export, tools
from app.services.call_state import build_call_report


def make_report(db, call, form):
    for field_id, value in [("caller_name", "Test Person"), ("age", "30"), ("number_of_children", "2")]:
        tools.save_answer(db, call, form, {"field_id": field_id, "value": value, "confidence": "high"})
    db.add(Review(call_id=call.id, field_id="age", mark="correct"))
    db.add(Review(call_id=call.id, field_id="caller_name", mark="wrong", expected_value="Test Person Two"))
    db.commit()
    return build_call_report(db, call, form)


def test_scores(db, call, form):
    scores = make_report(db, call, form)["scores"]
    assert scores["filled_fields"] == 3
    assert scores["correct_fields"] == 1
    assert scores["accuracy"] == round(1 / 3, 3)
    # Required & active: 7 base required + children_ages (2 children) = 8; 3 filled.
    assert scores["required_total"] == 8
    assert scores["completion"] == round(3 / 8, 3)


def test_json_export_round_trips(db, call, form):
    report = make_report(db, call, form)
    data = json.loads(export.to_json(report))
    assert data["call"]["id"] == call.id
    age = next(f for f in data["fields"] if f["id"] == "age")
    assert age["value"] == 30 and age["review"]["mark"] == "correct"


def test_csv_export(db, call, form):
    text = export.to_csv(make_report(db, call, form))
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == export.CSV_COLUMNS
    by_id = {r[0]: r for r in rows[1:] if len(r) == len(export.CSV_COLUMNS)}
    assert by_id["caller_name"][7] == "wrong"
    assert by_id["caller_name"][8] == "Test Person Two"
    assert by_id["age"][5] == "30"
    # Summary block after the field rows
    assert ["accuracy", "0.333"] in rows
