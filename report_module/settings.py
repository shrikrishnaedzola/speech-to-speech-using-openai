"""Load report settings (weights, rates, options) from settings.json."""
import json
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_SETTINGS_PATH = MODULE_DIR / "settings.json"


def load_settings(path: str | Path | None = None) -> dict:
    """Read settings.json. Pass a path to use a tester-specific copy."""
    return json.loads(Path(path or DEFAULT_SETTINGS_PATH).read_text(encoding="utf-8"))
