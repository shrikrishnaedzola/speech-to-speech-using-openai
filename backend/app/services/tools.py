"""The four voice-agent tools, and their JSON schemas.

Every tool returns a dict. The browser sends json.dumps(result) back to the
model as the function output, so the messages here are written for the agent
to read (e.g. "Politely ask again ...").
"""
import json

from sqlalchemy.orm import Session

from ..models import Answer, Call
from . import form_logic
from .call_state import answer_rows, answers_map, next_field

TOOL_NAMES = ("save_answer", "request_clarification", "skip_field", "complete_form")


def tool_schemas(form: dict, strict: bool = True) -> list[dict]:
    """Function tool definitions for the selected form.

    Strict mode rules (OpenAI function calling docs): every object needs
    additionalProperties: false and every property must be in "required".
    `value` is a string because strict schemas have no "any" type; the
    backend converts it to the right type (number, yes/no, list...).
    """
    field_ids = [f["id"] for f in form["fields"]]
    field_id_schema = {"type": "string", "enum": field_ids, "description": "Id of the form field."}

    def fn(name: str, description: str, properties: dict) -> dict:
        tool = {
            "type": "function",
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        }
        if strict:
            tool["strict"] = True
        return tool

    return [
        fn(
            "save_answer",
            "Save the caller's answer to one form field. Call right after each answer, "
            "and again if the caller corrects an earlier answer.",
            {
                "field_id": field_id_schema,
                "value": {
                    "type": "string",
                    "description": "The answer as text. Numbers as digits ('34'). Yes/no as 'yes' or 'no'. "
                                   "Lists as comma-separated numbers ('4, 7').",
                },
                "confidence": {
                    "type": "string",
                    "enum": ["high", "low"],
                    "description": "low if you are not sure you heard it correctly.",
                },
            },
        ),
        fn(
            "request_clarification",
            "Mark a field as needing confirmation when the answer was unclear.",
            {"field_id": field_id_schema, "reason": {"type": "string"}},
        ),
        fn(
            "skip_field",
            "Skip an OPTIONAL field when the caller does not want to answer. Not allowed for required fields.",
            {"field_id": field_id_schema, "reason": {"type": "string"}},
        ),
        fn(
            "complete_form",
            "Call at the end, after reading back the key answers. Returns missing required fields if any.",
            {},
        ),
    ]


def _upsert_answer(db: Session, call_id: int, field_id: str, **values) -> Answer:
    row = answer_rows(db, call_id).get(field_id)
    if row is None:
        row = Answer(call_id=call_id, field_id=field_id)
        db.add(row)
    for key, value in values.items():
        setattr(row, key, value)
    db.commit()
    return row


def _next_hint(db: Session, call_id: int, form: dict) -> dict | None:
    field = next_field(form, answer_rows(db, call_id))
    return {"field_id": field["id"], "question": field.get("question", field["label"])} if field else None


def _error(message: str, field: dict | None = None) -> dict:
    result = {"ok": False, "error": message, "instruction": "Politely explain and ask the question again."}
    if field:
        result["question"] = field.get("question", field.get("label"))
    return result


def save_answer(db: Session, call: Call, form: dict, args: dict) -> dict:
    field = form_logic.get_field(form, args.get("field_id", ""))
    if field is None:
        return _error(f"Unknown field_id '{args.get('field_id')}'.")

    rows = answer_rows(db, call.id)
    values = answers_map(rows)
    if not form_logic.is_active(field, values):
        cond = form_logic.describe_condition(field["condition"])
        return {"ok": False, "error": f"Do not ask {field['id']}: it is only asked when {cond}."}

    raw = args.get("value")
    try:
        value = form_logic.parse_value(field, raw, values)
    except form_logic.FieldValueError as exc:
        return _error(str(exc), field)

    confidence = args.get("confidence") or "high"
    status = "needs_confirmation" if confidence == "low" else "filled"
    _upsert_answer(
        db, call.id, field["id"],
        value_json=json.dumps(value),
        raw_value=None if raw is None else str(raw),
        confidence=confidence,
        status=status,
        reason=None,
    )
    result = {"ok": True, "saved": field["id"], "value": value, "next": _next_hint(db, call.id, form)}
    if status == "needs_confirmation":
        result["instruction"] = "Confidence is low: confirm this answer with the caller, then save it again."
    return result


def request_clarification(db: Session, call: Call, form: dict, args: dict) -> dict:
    field = form_logic.get_field(form, args.get("field_id", ""))
    if field is None:
        return _error(f"Unknown field_id '{args.get('field_id')}'.")
    _upsert_answer(db, call.id, field["id"], status="needs_confirmation", reason=args.get("reason"))
    return {"ok": True, "field_id": field["id"], "question": field.get("question", field["label"])}


def skip_field(db: Session, call: Call, form: dict, args: dict) -> dict:
    field = form_logic.get_field(form, args.get("field_id", ""))
    if field is None:
        return _error(f"Unknown field_id '{args.get('field_id')}'.")
    if field.get("required"):
        return _error(f"{field['id']} is required and cannot be skipped.", field)
    _upsert_answer(
        db, call.id, field["id"],
        status="skipped", value_json=None, raw_value=None, confidence=None, reason=args.get("reason"),
    )
    return {"ok": True, "skipped": field["id"], "next": _next_hint(db, call.id, form)}


def complete_form(db: Session, call: Call, form: dict, args: dict) -> dict:
    rows = answer_rows(db, call.id)
    missing = form_logic.missing_required(form, answers_map(rows))
    if missing:
        return {
            "ok": False,
            "error": "Some required fields are missing.",
            "missing_fields": [
                {"field_id": fid, "question": form_logic.get_field(form, fid).get("question")} for fid in missing
            ],
            "instruction": "Ask these questions before completing.",
        }
    unconfirmed = [fid for fid, row in rows.items() if row.status == "needs_confirmation"]
    call.form_completed = True
    db.commit()
    return {
        "ok": True,
        "message": "Form complete. Thank the caller and end the call politely.",
        "unconfirmed_fields": unconfirmed,
    }


HANDLERS = {
    "save_answer": save_answer,
    "request_clarification": request_clarification,
    "skip_field": skip_field,
    "complete_form": complete_form,
}


def run_tool(db: Session, call: Call, form: dict, name: str, args: dict) -> dict:
    handler = HANDLERS.get(name)
    if handler is None:
        return {"ok": False, "error": f"Unknown tool '{name}'."}
    return handler(db, call, form, args)
