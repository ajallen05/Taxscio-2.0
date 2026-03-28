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


def _migrate_checklist_table() -> None:
    """Create / evolve client_document_checklist and client_checklist_questions."""
    if not engine:
        return
    migrations = [
        # ── client_document_checklist ─────────────────────────────────────────
        """
        CREATE TABLE IF NOT EXISTS client_document_checklist (
            id             VARCHAR      PRIMARY KEY,
            client_id      VARCHAR      NOT NULL,
            tax_year       INTEGER      NOT NULL,
            form_name      VARCHAR(100) NOT NULL,
            expected_count INTEGER      NOT NULL DEFAULT 1,
            confidence     VARCHAR(50),
            trigger_line   VARCHAR(200),
            trigger_value  VARCHAR(500),
            source         VARCHAR(50)  NOT NULL DEFAULT 'manual',
            document_class VARCHAR(50)  NOT NULL DEFAULT 'filing_form',
            derived_from_unverified_data VARCHAR(5) NOT NULL DEFAULT 'false',
            created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_ledger_doc_checklist UNIQUE (client_id, tax_year, form_name)
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_ledger_doc_checklist_client_year ON client_document_checklist (client_id, tax_year)",
        "CREATE INDEX IF NOT EXISTS ix_ledger_doc_checklist_client_id   ON client_document_checklist (client_id)",
        # Safe ADD COLUMN for existing installs
        "ALTER TABLE client_document_checklist ADD COLUMN IF NOT EXISTS confidence    VARCHAR(50)",
        "ALTER TABLE client_document_checklist ADD COLUMN IF NOT EXISTS trigger_line  VARCHAR(200)",
        "ALTER TABLE client_document_checklist ADD COLUMN IF NOT EXISTS trigger_value VARCHAR(500)",
        "ALTER TABLE client_document_checklist ADD COLUMN IF NOT EXISTS source        VARCHAR(50) NOT NULL DEFAULT 'manual'",
        "ALTER TABLE client_document_checklist ADD COLUMN IF NOT EXISTS document_class VARCHAR(50) NOT NULL DEFAULT 'filing_form'",
        "ALTER TABLE client_document_checklist ADD COLUMN IF NOT EXISTS derived_from_unverified_data VARCHAR(5) NOT NULL DEFAULT 'false'",

        # ── client_checklist_questions ────────────────────────────────────────
        """
        CREATE TABLE IF NOT EXISTS client_checklist_questions (
            id              VARCHAR      PRIMARY KEY,
            client_id       VARCHAR      NOT NULL,
            tax_year        INTEGER      NOT NULL,
            question_id     VARCHAR(100) NOT NULL,
            trigger_line    VARCHAR(200),
            trigger_value   VARCHAR(500),
            question_text   TEXT         NOT NULL,
            options_json    JSONB        NOT NULL DEFAULT '[]',
            status          VARCHAR(50)  NOT NULL DEFAULT 'pending_client_response',
            selected_option VARCHAR(200),
            resolved_forms  JSONB,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_checklist_question UNIQUE (client_id, tax_year, question_id)
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_checklist_question_client_year ON client_checklist_questions (client_id, tax_year)",
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
        _migrate_checklist_table()
