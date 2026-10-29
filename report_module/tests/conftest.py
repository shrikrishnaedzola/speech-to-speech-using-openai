import json
import sys
from pathlib import Path

import pytest

# Allow running from the repo root without installing (pip install -e also works).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from report_module.call_data import CallData  # noqa: E402
from report_module.settings import load_settings  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
PROVIDERS = ["openai", "sarvam", "gemini", "elevenlabs"]


def load_sample(name: str) -> CallData:
    return CallData.model_validate(json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8")))


@pytest.fixture
def settings():
    return load_settings()


def minimal_call(**overrides) -> CallData:
    """A tiny valid call for unit tests."""
    data = {
        "call": {"call_id": "t1", "provider": "openai", "model": "gpt-live-1", "language": "English",
                 "started_at": "2026-10-27T10:00:00+05:30", "duration_s": 120},
    }
    data.update(overrides)
    return CallData.model_validate(data)
