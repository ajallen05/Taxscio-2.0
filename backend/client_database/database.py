"""
client_database/database.py
SQLAlchemy engine & session for the `client_database` PostgreSQL database.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

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


def init_db():
    """Create all tables (enum_master + clients) if they don't exist."""
    if engine:
        Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yield a DB session and close it after the request."""
    if SessionLocal is None:
        raise RuntimeError("CLIENT_DATABASE_URL not configured — client database unavailable.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
