"""Shared test fixtures: the sample form and an in-memory database."""
import json
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
# Use an in-memory database so tests never touch data/app.db. Must be set before importing app.
os.environ["DATABASE_URL"] = "sqlite://"

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db import Base  # noqa: E402
from app.models import Call  # noqa: E402
from app.services.forms import seed_forms  # noqa: E402

SEED_DIR = BACKEND_DIR / "seed_forms"


@pytest.fixture
def form():
    return json.loads((SEED_DIR / "program_feedback_survey.json").read_text(encoding="utf-8"))


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    seed_forms(session, SEED_DIR)
    yield session
    session.close()


@pytest.fixture
def call(db):
    row = Call(form_id="program_feedback_survey", mode="simulate", model="simulate",
               language="English", voice="marin", cost_rate_per_min=0.05)
    db.add(row)
    db.commit()
    return row
