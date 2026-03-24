from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, JSON, Float, DateTime
from .database import Base

class Ledger(Base):
    __tablename__ = "ledger"
    id = Column(Integer, primary_key=True)
    document_id = Column(String, unique=True)
    client_name = Column(String)
    document_type = Column(String)
    provider = Column(String)
    description = Column(Text)
    source = Column(String)
    tax_year = Column(Integer)
    stage = Column(String)
    status = Column(String)
    version = Column(Integer)
    upload_count = Column(Integer, default=1)
    content_hash = Column(String)
    audit_trail = Column(JSON)
    cpa = Column(String)
    due_date = Column(String)
    confidence_score = Column(Float)


class DocumentLog(Base):
    __tablename__ = "document_logs"
    id = Column(Integer, primary_key=True)
    document_id = Column(String)
    version = Column(Integer)
    upload_count = Column(Integer, default=1)
    content_hash = Column(String)
    client_name = Column(String)
    document_type = Column(String)
    provider = Column(String)
    description = Column(Text)
    source = Column(String)
    tax_year = Column(Integer)
    stage = Column(String)
    status = Column(String)
    cpa = Column(String)
    due_date = Column(String)
    confidence_score = Column(Float)


class ExceptionEscalation(Base):
    """CPA escalation events from the Exceptions UI (persisted server-side)."""
    __tablename__ = "exception_escalations"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    document_id = Column(String, nullable=True)
    client_name = Column(String, nullable=True)
    document_type = Column(String, nullable=True)
    filename = Column(String, nullable=True)
    exception_code = Column(String, nullable=True)
    exception_field = Column(String, nullable=True)
    severity = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    payload = Column(JSON, nullable=True)
