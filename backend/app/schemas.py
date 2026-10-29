"""Request bodies for the API (validated by FastAPI/Pydantic)."""
from typing import Any, Literal

from pydantic import BaseModel, Field


class CreateCallRequest(BaseModel):
    form_id: str
    mode: Literal["live", "realtime", "simulate"]
    language: str = "English"
    voice: str = "marin"
    delegate_model: str | None = None  # GPT-Live only; defaults to LIVE_DELEGATE_MODEL
    cost_rate_per_min: float | None = None
    audio_mode: Literal["normal", "phone_8khz"] = "normal"


class SessionRequest(BaseModel):
    call_id: int
    sdp: str = Field(..., description="Browser WebRTC SDP offer")


class ToolRequest(BaseModel):
    call_id: int
    arguments: dict[str, Any] = {}


class TurnRequest(BaseModel):
    latency_ms: float
    ts_ms: float | None = None  # when the agent reply started, ms since the call connected


class EndCallRequest(BaseModel):
    duration_s: float
    interruptions: int = 0
    usage_seconds: float | None = None
    transcript: list[dict[str, Any]] = []
    failed: bool = False
    client_started_at: str | None = None  # ISO time the browser connected (time zero for the report)
    events: list[dict[str, Any]] = []  # e.g. [{"type": "barge_in", "ts_ms": 41250}]


class ReviewRequest(BaseModel):
    field_id: str
    mark: Literal["correct", "wrong"] | None  # None clears the mark
    expected_value: str | None = None
