"""CallData: the ONE input format every tester must produce.

Each tester (OpenAI, Sarvam, Gemini, ElevenLabs) writes a small adapter that
reads its own database and returns a CallData. Everything after that is shared,
so reports from all providers look the same.

Times: `ts_ms` = milliseconds since the call started (connected). Optional
fields can be left out; the report then shows "not available" for them.
"""
from typing import Any, Literal

from pydantic import BaseModel, Field

CALL_DATA_VERSION = "1.0"


class CallInfo(BaseModel):
    call_id: str
    provider: Literal["openai", "sarvam", "gemini", "elevenlabs"]
    model: str
    voice: str | None = None
    language: str  # language selected for the call, e.g. "Hindi"
    audio_mode: Literal["normal", "phone_8khz"] = "normal"
    started_at: str  # ISO 8601 date-time
    duration_s: float | None = None
    form_name: str | None = None
    form_completed: bool = False


class Turn(BaseModel):
    """One transcript bubble."""
    role: Literal["caller", "agent"]
    text: str
    ts_ms: float | None = None
    detected_language: str | None = None  # if the provider reports it; else detected locally


class FormField(BaseModel):
    id: str
    label: str
    type: str = "text"  # text / number / choice / yes_no / list_number
    required: bool = False
    condition: str | None = None  # e.g. "attended_sessions = yes" (follow-up fields only)
    active: bool = True  # condition met at the end of the call
    status: str = "pending"  # pending / filled / needs_confirmation / skipped
    saved_value: Any = None
    expected_value: Any = None  # typed by the tester, or from the scenario
    review_mark: Literal["correct", "wrong"] | None = None


class TurnMetric(BaseModel):
    turn: int
    latency_ms: float  # caller stops speaking -> first agent audio
    ts_ms: float | None = None
    stt_ms: float | None = None  # Sarvam (cascaded) only
    llm_ms: float | None = None
    tts_ms: float | None = None


class ToolCallRecord(BaseModel):
    name: str
    arguments: dict[str, Any] = {}
    success: bool
    result: dict[str, Any] = {}
    duration_ms: float | None = None
    ts_ms: float | None = None


class Usage(BaseModel):
    """Whatever the provider reports. Cost rates in settings.json refer to these keys."""
    voice_seconds: float | None = None
    audio_in_seconds: float | None = None
    audio_out_seconds: float | None = None
    audio_in_tokens: float | None = None
    audio_out_tokens: float | None = None
    llm_input_tokens: float | None = None
    llm_output_tokens: float | None = None
    tts_characters: float | None = None
    stt_seconds: float | None = None


class Event(BaseModel):
    """Timeline events, e.g. {"type": "barge_in", "ts_ms": 41250}."""
    type: str
    ts_ms: float
    detail: str | None = None


class Ratings(BaseModel):
    """Tester ratings, 1-5. Any can be missing."""
    naturalness: int | None = Field(None, ge=1, le=5)
    clarity: int | None = Field(None, ge=1, le=5)
    pronunciation: int | None = Field(None, ge=1, le=5)
    accent_fit: int | None = Field(None, ge=1, le=5)
    politeness: int | None = Field(None, ge=1, le=5)
    code_mixing: int | None = Field(None, ge=1, le=5)
    notes: str | None = None


class Scenario(BaseModel):
    """Optional expected caller script (from the comparison tool's scenarios)."""
    id: str
    name: str | None = None
    caller_script: list[str] = []  # what the caller is expected to say, in order
    expected_answers: dict[str, Any] = {}


class CallData(BaseModel):
    version: str = CALL_DATA_VERSION
    call: CallInfo
    transcript: list[Turn] = []
    fields: list[FormField] = []
    turn_metrics: list[TurnMetric] = []
    tool_calls: list[ToolCallRecord] = []
    usage: Usage = Usage()
    interruptions: int = 0
    events: list[Event] = []
    ratings: Ratings = Ratings()
    scenario: Scenario | None = None
    agent_audio_path: str | None = None  # WAV file of the agent's voice (dummy calls only)
