"""
client_database/database.py
SQLAlchemy engine & session for the `client_database` PostgreSQL database.
"""
import logging
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

log = logging.getLogger("Taxscio.client_database.database")

# Dedicated DATABASE_URL for the client database.
# Falls back to the existing DATABASE_URL but swaps the db name to client_database.
_raw_url = os.environ.get("CLIENT_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
CLIENT_DATABASE_URL = ""
if _raw_url:
    # Replace the db name at the end of the URL (after the last '/')
    parts = _raw_url.rsplit("/", 1)
    CLIENT_DATABASE_URL = parts[0] + "/client_database" if len(parts) == 2 else _raw_url

engine = None
SessionLocal = None
Base = declarative_base()

if CLIENT_DATABASE_URL:
    engine = create_engine(
        CLIENT_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _migrate_checklist_columns() -> None:
    """
    Add FDR columns to client_document_checklist if they don't exist.

    No Alembic in this project — we perform safe ADD COLUMN migrations at
    startup.  Each statement is wrapped in its own transaction so a
    'column already exists' error is swallowed gracefully.

    Columns added:
        confidence    VARCHAR(50)   DEFAULT NULL
        trigger_line  VARCHAR(200)  DEFAULT NULL
        trigger_value VARCHAR(500)  DEFAULT NULL
        source        VARCHAR(50)   DEFAULT 'manual'
    """
    if not engine:
        return

    migrations = [
        "ALTER TABLE client_document_checklist ADD COLUMN confidence    VARCHAR(50)  DEFAULT NULL",
        "ALTER TABLE client_document_checklist ADD COLUMN trigger_line  VARCHAR(200) DEFAULT NULL",
        "ALTER TABLE client_document_checklist ADD COLUMN trigger_value VARCHAR(500) DEFAULT NULL",
        "ALTER TABLE client_document_checklist ADD COLUMN source        VARCHAR(50)  NOT NULL DEFAULT 'manual'",
    ]
    for stmt in migrations:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
            log.info("Migration applied: %s", stmt[:70])
        except Exception:
            # Column already exists or table doesn't exist yet — both are fine
            pass


def init_db():
    """Create all tables and apply FDR column migrations."""
    if engine:
        Base.metadata.create_all(bind=engine)
        _migrate_checklist_columns()


def get_db():
    """FastAPI dependency: yield a DB session and close it after the request."""
    if SessionLocal is None:
        raise RuntimeError("CLIENT_DATABASE_URL not configured — client database unavailable.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
