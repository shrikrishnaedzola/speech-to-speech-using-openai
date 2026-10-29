"""End-to-end: a simulated call through the API produces a post-call report automatically."""
import struct

import pytest
from fastapi.testclient import TestClient

from app.main import app

ANSWERS = [
    ("caller_name", "Test Person"), ("age", "150"), ("age", "30"), ("district", "Sample District"),
    ("attended_sessions", "yes"), ("sessions_attended_count", "50"), ("sessions_attended_count", "15"),
    ("number_of_children", "0"), ("satisfaction_rating", "4"), ("consent_to_followup", "yes"),
]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def ended_call(client):
    call_id = client.post("/api/calls", json={"form_id": "program_feedback_survey", "mode": "simulate",
                                              "audio_mode": "phone_8khz"}).json()["call_id"]
    for field_id, value in ANSWERS:
        client.post("/api/tools/save_answer", json={"call_id": call_id, "arguments":
                    {"field_id": field_id, "value": value, "confidence": "high"}})
    client.post("/api/tools/complete_form", json={"call_id": call_id, "arguments": {}})
    for i, ms in enumerate([900, 1400, 2100]):
        client.post(f"/api/calls/{call_id}/turns", json={"latency_ms": ms, "ts_ms": 5000 * (i + 1)})
    end = client.post(f"/api/calls/{call_id}/end", json={
        "duration_s": 95, "interruptions": 1, "client_started_at": "2026-10-28T10:00:00+00:00",
        "events": [{"type": "barge_in", "ts_ms": 12000}],
        "transcript": [
            {"role": "agent", "text": "How many sessions did you attend?", "ts": "2026-10-28T10:00:20+00:00"},
            {"role": "caller", "text": "No, I said fifteen, not fifty.", "ts": "2026-10-28T10:00:30+00:00"},
        ],
    }).json()
    return call_id, end


def test_report_generated_on_end(client, ended_call):
    call_id, end = ended_call
    assert end["report_ready"] is True
    report = client.get(f"/api/calls/{call_id}/report").json()
    assert report["call"]["provider"] == "openai" and report["call"]["audio_mode"] == "phone_8khz"
    assert report["latency"]["avg_ms"] == 1467
    assert report["accuracy"]["invalid_answers"] == 1 and report["accuracy"]["invalid_answers_recovered"] == 1
    # 50 -> 15 change = a fixed teen/ty mishearing on sessions_attended_count.
    # (Exact totals depend on wall-clock tool-call times, so check the item itself.)
    number_items = [i for i in report["mishearings"]["items"] if i["field_id"] == "sessions_attended_count"]
    assert number_items and number_items[0]["fixed"] is True
    assert number_items[0]["number_issue"].startswith("teen/ty")


def test_ratings_regenerate_report(client, ended_call):
    call_id, _ = ended_call
    report = client.post(f"/api/calls/{call_id}/ratings", json={"naturalness": 4, "clarity": 5, "code_mixing": 3}).json()
    assert report["voice_quality"]["ratings"]["clarity"] == 5
    assert report["language"]["code_mixing_rating"] == 3
    assert report["summary"]["parts"]["voice_quality"] is not None


def test_review_marks_flow_into_report(client, ended_call):
    call_id, _ = ended_call
    client.post(f"/api/calls/{call_id}/review", json={"field_id": "district", "mark": "wrong",
                                                       "expected_value": "Other District"})
    report = client.post(f"/api/calls/{call_id}/report").json()
    row = next(r for r in report["accuracy"]["table"] if r["field_id"] == "district")
    assert row["correct"] is False and row["expected"] == "Other District"


@pytest.mark.parametrize("fmt, media", [("json", "application/json"), ("md", "text/markdown")])
def test_exports(client, ended_call, fmt, media):
    call_id, _ = ended_call
    res = client.get(f"/api/calls/{call_id}/report/export?format={fmt}")
    assert res.status_code == 200 and res.headers["content-type"].startswith(media)
    assert f'report_openai_simulate_English_' in res.headers["content-disposition"]
    assert "TEST MODE - dummy data only" in res.text


def test_audio_upload(client, ended_call, tmp_path, monkeypatch):
    from app.routers import calls
    monkeypatch.setattr(calls, "AUDIO_DIR", tmp_path)  # keep test files out of data/audio
    call_id, _ = ended_call
    # 0.1 s of silence, 16 kHz mono 16-bit WAV
    samples = b"\x00\x00" * 1600
    header = b"RIFF" + struct.pack("<I", 36 + len(samples)) + b"WAVEfmt " + struct.pack(
        "<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16) + b"data" + struct.pack("<I", len(samples))
    res = client.post(f"/api/calls/{call_id}/audio", content=header + samples)
    assert res.json()["saved"] is True
    assert client.post(f"/api/calls/{call_id}/audio", content=b"not a wav").status_code == 400


def test_unknown_call(client):
    assert client.get("/api/calls/99999/report").status_code == 404
