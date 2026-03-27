import os
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL")

engine = None
SessionLocal = None
Base = declarative_base()

if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)

def _migrate_ledger_client_id() -> None:
    """Idempotently add client_id column to ledger + document_logs tables."""
    if not engine:
        return
    migrations = [
        "ALTER TABLE ledger        ADD COLUMN IF NOT EXISTS client_id VARCHAR",
        "ALTER TABLE document_logs ADD COLUMN IF NOT EXISTS client_id VARCHAR",
        "CREATE INDEX IF NOT EXISTS ix_ledger_client_id ON ledger (client_id)",
        "ALTER TABLE ledger        ADD COLUMN IF NOT EXISTS extraction_json_path VARCHAR",
        "ALTER TABLE document_logs ADD COLUMN IF NOT EXISTS extraction_json_path VARCHAR",
    ]
    with engine.begin() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
            except Exception:
                pass


def init_db():
    if engine:
        from . import models  # noqa: F401 — register ledger tables
        Base.metadata.create_all(bind=engine)
        # Legacy cleanup: escalation events now live only in ledger.audit_trail.
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS exception_escalations"))
        _migrate_ledger_client_id()
