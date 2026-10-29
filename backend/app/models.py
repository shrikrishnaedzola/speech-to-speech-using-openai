"""SQLite tables: forms, calls, answers, tool_calls, turn_metrics, reviews."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def now():
    return datetime.now(timezone.utc)


class Form(Base):
    __tablename__ = "forms"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "program_feedback_survey"
    name: Mapped[str] = mapped_column(String)
    definition_json: Mapped[str] = mapped_column(Text)  # the full form JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Call(Base):
    __tablename__ = "calls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    form_id: Mapped[str] = mapped_column(ForeignKey("forms.id"))
    mode: Mapped[str] = mapped_column(String)  # "live" | "realtime" | "simulate"
    model: Mapped[str] = mapped_column(String)
    delegate_model: Mapped[str | None] = mapped_column(String, nullable=True)
    language: Mapped[str] = mapped_column(String)
    voice: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="created")  # created/connected/ended/failed
    openai_session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    form_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    interruptions: Mapped[int] = mapped_column(Integer, default=0)
    usage_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)  # billed seconds reported by OpenAI
    cost_rate_per_min: Mapped[float] = mapped_column(Float, default=0.0)
    transcript_json: Mapped[str] = mapped_column(Text, default="[]")
    # Added for the post-call report (report_module):
    audio_mode: Mapped[str | None] = mapped_column(String, nullable=True, default="normal")  # normal / phone_8khz
    client_started_at: Mapped[str | None] = mapped_column(String, nullable=True)  # browser time zero (ISO)
    events_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # [{"type": "barge_in", "ts_ms": ...}]
    agent_audio_path: Mapped[str | None] = mapped_column(String, nullable=True)  # WAV of the agent's voice


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("call_id", "field_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"))
    field_id: Mapped[str] = mapped_column(String)
    value_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # parsed value as JSON
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)  # what the agent sent
    confidence: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)  # filled / needs_confirmation / skipped
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class ToolCall(Base):
    __tablename__ = "tool_calls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"))
    name: Mapped[str] = mapped_column(String)
    arguments_json: Mapped[str] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(Boolean)
    result_json: Mapped[str] = mapped_column(Text)
    duration_ms: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class TurnMetric(Base):
    __tablename__ = "turn_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"))
    turn_index: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[float] = mapped_column(Float)  # caller stops speaking -> first agent audio
    ts_ms: Mapped[float | None] = mapped_column(Float, nullable=True)  # ms since the call connected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("call_id", "field_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"))
    field_id: Mapped[str] = mapped_column(String)
    mark: Mapped[str] = mapped_column(String)  # "correct" | "wrong"
    expected_value: Mapped[str | None] = mapped_column(Text, nullable=True)


class CallRatings(Base):
    """Tester 1-5 ratings for the post-call report (voice quality + code-mixing)."""
    __tablename__ = "call_ratings"
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"), primary_key=True)
    ratings_json: Mapped[str] = mapped_column(Text)


class CallReport(Base):
    """Latest generated post-call report (report_module JSON)."""
    __tablename__ = "call_reports"
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"), primary_key=True)
    report_json: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
