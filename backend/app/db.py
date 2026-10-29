"""Database engine and session helper (SQLite via SQLAlchemy)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import BACKEND_DIR, settings


def _resolve_url(url: str) -> str:
    # Make "sqlite:///./data/app.db" relative to backend/, not the shell's cwd.
    prefix = "sqlite:///./"
    if url.startswith(prefix):
        path = BACKEND_DIR / url[len(prefix):]
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"
    return url


_url = _resolve_url(settings.database_url)
engine = create_engine(
    _url,
    connect_args={"check_same_thread": False},  # needed for SQLite + FastAPI
    # In-memory SQLite (tests): share ONE connection, otherwise each session gets an empty DB.
    poolclass=StaticPool if _url == "sqlite://" else None,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: one DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def add_missing_columns() -> None:
    """Tiny migration: add new nullable columns to tables created by an older version.

    create_all() makes new tables but never changes existing ones, so an older
    data/app.db would miss columns added later (e.g. for the post-call report).
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing and column.nullable:
                    col_type = column.type.compile(engine.dialect)
                    conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {col_type}'))
