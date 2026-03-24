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
