"""JSON export with ONE fixed schema for all providers (for the comparison tool).

The schema is report.schema.json next to this file. Bump SCHEMA_VERSION in
report_builder.py whenever a field is renamed or removed.
"""
import json
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "report.schema.json"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_report(report: dict) -> None:
    """Raise jsonschema.ValidationError if the report does not match the schema.

    Needs the optional `jsonschema` package (installed with the [test] extra).
    """
    import jsonschema

    jsonschema.validate(report, load_schema())


def to_json(report: dict) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False)
