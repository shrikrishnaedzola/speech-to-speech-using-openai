"""Database engine and session helper (SQLite via SQLAlchemy)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import BACKEND_DIR, settings


def _resolve_url(url: str) -> str:
    # "mysql://..." would make SQLAlchemy look for the MySQLdb driver, which we
    # don't install. Use PyMySQL (pure Python, in requirements.txt) instead.
    if url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[len("mysql://"):]
    # Make "sqlite:///./data/app.db" relative to backend/, not the shell's cwd.
    prefix = "sqlite:///./"
    if url.startswith(prefix):
        path = BACKEND_DIR / url[len(prefix):]
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"
    return url


def _engine_options(url: str) -> dict:
    if url.startswith("sqlite"):
        return {
            "connect_args": {"check_same_thread": False},  # needed for SQLite + FastAPI
            # In-memory SQLite (tests): share ONE connection, otherwise each session gets an empty DB.
            "poolclass": StaticPool if url == "sqlite://" else None,
        }
    # MySQL (deployed). pre_ping + recycle: serverless instances sit idle, and
    # MySQL closes idle connections, so check/refresh them before use.
    options = {"pool_pre_ping": True, "pool_recycle": 280, "pool_size": 2, "max_overflow": 3}
    if settings.database_ssl:
        import certifi  # installed with httpx

        options["connect_args"] = {"ssl": {"ca": certifi.where()}}
    return options


if settings.on_vercel and settings.database_url.startswith("sqlite"):
    # Vercel's disk is read-only and wiped between requests: SQLite would lose everything.
    raise RuntimeError("Set DATABASE_URL to your MySQL database in the Vercel project settings.")

_url = _resolve_url(settings.database_url)
engine = create_engine(_url, **_engine_options(_url))
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
                    quote = engine.dialect.identifier_preparer.quote  # "x" on SQLite, `x` on MySQL
                    conn.execute(text(f"ALTER TABLE {quote(table.name)} ADD COLUMN {quote(column.name)} {col_type}"))


def check_mysql_charset() -> str | None:
    """Warn if the MySQL database is not utf8mb4 (Hindi/Tamil text would be garbled or rejected)."""
    if engine.dialect.name != "mysql":
        return None
    from sqlalchemy import text

    with engine.connect() as conn:
        charset = conn.execute(text("SELECT @@character_set_database")).scalar()
    if charset != "utf8mb4":
        return (f"MySQL database charset is {charset}, not utf8mb4. Run: ALTER DATABASE <name> "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    return None


DB_HINTS = [
    ("can't connect", "MySQL server not reachable from Vercel. It must accept remote connections "
                      "(not localhost / your PC / an office network) on port 3306."),
    ("timed out", "MySQL server not reachable from Vercel (connection timed out). Check host, port and firewall."),
    ("access denied", "Wrong MySQL user/password, or the user is not allowed from outside ('user'@'%')."),
    ("unknown database", "The database name in DATABASE_URL does not exist. Create it or fix the name."),
    ("ssl", "TLS problem: try switching DATABASE_SSL between true and false to match your MySQL server."),
    ("name or service not known", "The MySQL host name in DATABASE_URL is wrong (DNS lookup failed)."),
    ("nodename nor servname", "The MySQL host name in DATABASE_URL is wrong (DNS lookup failed)."),
]


def describe_db_error(exc: Exception) -> str:
    """One-line, password-free description of a database error, with a hint."""
    from sqlalchemy.engine import make_url

    text = f"{type(exc).__name__}: {getattr(exc, 'orig', None) or exc}"
    try:
        password = make_url(_url).password
        if password:
            text = text.replace(password, "***")
    except Exception:
        pass
    text = text.splitlines()[0][:300] if text else text  # first line only: SQLAlchemy appends SQL and links
    hint = next((h for key, h in DB_HINTS if key in text.lower()), None)
    return f"{text} -> {hint}" if hint else text
