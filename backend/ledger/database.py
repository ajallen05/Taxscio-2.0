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

def init_db():
    if engine:
        from . import models  # noqa: F401 — register ledger tables
        Base.metadata.create_all(bind=engine)
        # Legacy cleanup: escalation events now live only in ledger.audit_trail.
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS exception_escalations"))
            # Ensure client_id linkage exists and remove legacy payload columns.
            statements = [
                "ALTER TABLE ledger ADD COLUMN IF NOT EXISTS client_id VARCHAR",
                "ALTER TABLE document_logs ADD COLUMN IF NOT EXISTS client_id VARCHAR",
                "ALTER TABLE ledger ADD COLUMN IF NOT EXISTS local_json_path VARCHAR",
                "ALTER TABLE document_logs ADD COLUMN IF NOT EXISTS local_json_path VARCHAR",
                "ALTER TABLE ledger DROP COLUMN IF EXISTS extraction_data",
                "ALTER TABLE ledger DROP COLUMN IF EXISTS validation_data",
                "ALTER TABLE ledger DROP COLUMN IF EXISTS content_data",
                "ALTER TABLE document_logs DROP COLUMN IF EXISTS extraction_data",
                "ALTER TABLE document_logs DROP COLUMN IF EXISTS validation_data",
                "ALTER TABLE document_logs DROP COLUMN IF EXISTS content_data",
            ]
            for stmt in statements:
                try:
                    conn.execute(text(stmt))
                except Exception:
                    # Keep startup resilient across non-Postgres backends.
                    pass
