"""Create OpenAI voice sessions from the backend.

Security: the browser only sends us its WebRTC SDP offer. We call OpenAI
with the API key here and return only the SDP answer + session id. The key
never leaves the server.

Docs relied on:
- GPT-Live over WebRTC: POST /v1/live/sessions with {session, transport:{type:"webrtc", sdp}}
  returns 201 {session:{id}, transport:{type, sdp}}.
  https://developers.openai.com/api/docs/guides/realtime-webrtc
  https://developers.openai.com/api/docs/guides/voice-webrtc?api=live
- GPT-Live tools go through Responses delegation (delegation.responses.tools):
  https://developers.openai.com/api/docs/guides/live-delegation
- gpt-realtime unified interface: server posts multipart {sdp, session} to
  POST /v1/realtime/calls and gets the SDP answer back.
  https://developers.openai.com/api/docs/guides/realtime-webrtc
"""
import json

import httpx

from ..config import settings
from . import prompt
from .tools import tool_schemas


class OpenAISessionError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def _headers() -> dict:
    if not settings.openai_api_key:
        raise OpenAISessionError(500, "OPENAI_API_KEY is not set on the backend (.env).")
    return {"Authorization": f"Bearer {settings.openai_api_key}"}


def _error_message(response: httpx.Response) -> str:
    # OpenAI error bodies look like {"error": {"message": ...}}; they never contain our key.
    try:
        return response.json()["error"]["message"]
    except Exception:
        return response.text[:500]


def build_live_session(form: dict, language: str, voice: str, delegate_model: str) -> dict:
    """Session config for GPT-Live. audio.format is omitted: WebRTC negotiates it via SDP."""
    return {
        "model": settings.live_model,
        "instructions": prompt.live_instructions(form, language),
        "audio": {"output": {"voice": voice}},
        "delegation": {
            "type": "responses",
            "responses": {
                "model": delegate_model,
                "instructions": prompt.live_backend_instructions(form, language),
                "tools": tool_schemas(form, strict=True),
                "tool_choice": "auto",
                # One call per backend response keeps the browser tool loop simple.
                "parallel_tool_calls": False,
            },
        },
    }


def build_realtime_session(form: dict, language: str, voice: str) -> dict:
    """Session config for gpt-realtime-2.1 (tools are called by the voice model itself)."""
    return {
        "type": "realtime",
        "model": settings.realtime_model,
        "instructions": prompt.realtime_instructions(form, language),
        "audio": {
            "input": {
                "transcription": {"model": settings.realtime_transcribe_model},
                "turn_detection": {"type": "semantic_vad"},
            },
            "output": {"voice": voice},
        },
        # The Realtime function-calling guide does not document "strict",
        # so we send plain schemas; the backend validates every value anyway.
        "tools": tool_schemas(form, strict=False),
        "tool_choice": "auto",
    }


async def create_live_session(sdp_offer: str, session: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{settings.openai_base_url}/live/sessions",
            headers=_headers(),
            json={"session": session, "transport": {"type": "webrtc", "sdp": sdp_offer}},
        )
    if response.status_code >= 400:
        raise OpenAISessionError(response.status_code, _error_message(response))
    data = response.json()
    return {"session_id": data["session"]["id"], "sdp": data["transport"]["sdp"]}


async def create_realtime_call(sdp_offer: str, session: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{settings.openai_base_url}/realtime/calls",
            headers=_headers(),
            # multipart/form-data with two text parts: sdp and session (JSON)
            files={"sdp": (None, sdp_offer), "session": (None, json.dumps(session))},
        )
    if response.status_code >= 400:
        raise OpenAISessionError(response.status_code, _error_message(response))
    # The call id is the last part of the Location header, e.g. /v1/realtime/calls/rtc_123
    location = response.headers.get("Location", "")
    return {"session_id": location.rsplit("/", 1)[-1] or None, "sdp": response.text}
