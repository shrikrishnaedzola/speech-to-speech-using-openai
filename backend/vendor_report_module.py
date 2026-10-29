"""Vercel build step: copy ../report_module into backend/report_module.

On Vercel the backend service is built from the backend/ folder only, so the
shared report_module (a sibling folder) is copied in here before deploying.
Locally you do NOT need this: requirements-dev.txt installs ../report_module.
The copy is git-ignored.
"""
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "report_module"
TARGET = HERE / "report_module"

if not SOURCE.exists():
    raise SystemExit(f"report_module not found at {SOURCE}")
if TARGET.exists():
    shutil.rmtree(TARGET)
shutil.copytree(
    SOURCE,
    TARGET,
    # Tests, sample data and build files are not needed at runtime.
    ignore=shutil.ignore_patterns("tests", "samples", "__pycache__", "*.pyc", "*.egg-info", "pyproject.toml"),
)
print(f"Copied report_module into {TARGET}")
