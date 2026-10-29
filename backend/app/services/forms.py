"""Load form definitions from seed_forms/*.json into the database.

To add a new form: drop a JSON file (same shape as program_feedback_survey.json)
into backend/seed_forms/ and restart the backend.
"""
import json
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import Form


def validate_form_definition(form: dict) -> None:
    """Basic sanity checks so a broken JSON file fails loudly at startup."""
    for key in ("id", "name", "fields"):
        if key not in form:
            raise ValueError(f"Form is missing '{key}'")
    ids = [f["id"] for f in form["fields"]]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Form {form['id']} has duplicate field ids")
    for field in form["fields"]:
        cond = field.get("condition")
        if cond and cond["field"] not in ids:
            raise ValueError(f"Field {field['id']} has a condition on unknown field {cond['field']}")


def seed_forms(db: Session, folder: Path) -> int:
    """Insert or update every form JSON in the folder. Returns how many were loaded."""
    count = 0
    for path in sorted(folder.glob("*.json")):
        form = json.loads(path.read_text(encoding="utf-8"))
        validate_form_definition(form)
        row = db.get(Form, form["id"])
        if row is None:
            row = Form(id=form["id"])
            db.add(row)
        row.name = form["name"]
        row.definition_json = json.dumps(form)
        count += 1
    db.commit()
    return count


def load_form(db: Session, form_id: str) -> dict | None:
    row = db.get(Form, form_id)
    return json.loads(row.definition_json) if row else None
