"""Export a call report as JSON or CSV."""
import csv
import io
import json


def to_json(report: dict) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False)


CSV_COLUMNS = [
    "field_id", "label", "required", "active", "status", "value", "confidence",
    "review_mark", "expected_value",
]


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def to_csv(report: dict) -> str:
    """One row per form field, followed by a short summary block."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for f in report["fields"]:
        review = f["review"] or {}
        writer.writerow([
            f["id"], f["label"], _cell(f["required"]), _cell(f["active"]), f["status"],
            _cell(f["value"]), _cell(f["confidence"]), _cell(review.get("mark")), _cell(review.get("expected_value")),
        ])

    call, scores, metrics, cost = report["call"], report["scores"], report["metrics"], report["cost"]
    writer.writerow([])
    summary = [
        ("call_id", call["id"]), ("model", call["model"]), ("language", call["language"]),
        ("voice", call["voice"]), ("form_completed", call["form_completed"]),
        ("accuracy", scores["accuracy"]), ("completion", scores["completion"]),
        ("turns", metrics["turns"]), ("avg_latency_ms", metrics["avg_latency_ms"]),
        ("max_latency_ms", metrics["max_latency_ms"]), ("interruptions", metrics["interruptions"]),
        ("duration_s", metrics["duration_s"]), ("estimated_usd", cost["estimated_usd"]),
        ("tool_calls", len(report["tool_calls"])),
    ]
    for key, value in summary:
        writer.writerow([key, _cell(value)])
    return out.getvalue()
