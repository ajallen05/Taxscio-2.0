import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, JSON, Float, Index, DateTime, UniqueConstraint
from .database import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)

class Ledger(Base):
    __tablename__ = "ledger"
    id = Column(Integer, primary_key=True)
    document_id = Column(String, unique=True)
    client_id   = Column(String, nullable=True, index=True)   # FK → clients.id (cross-db reference)
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
    extraction_json_path = Column(String, nullable=True)  # relative path to local_extraction/<id>.json
    audit_trail = Column(JSON)
    cpa = Column(String)
    due_date = Column(String)
    confidence_score = Column(Float)


class ClientDocumentChecklist(Base):
    """
    Expected documents per client / tax year.
    Lives in the ledger DB so checklist data is co-located with document tracking.
    """
    __tablename__ = "client_document_checklist"

    id             = Column(String,  primary_key=True, default=_uuid)
    client_id      = Column(String,  nullable=False, index=True)
    tax_year       = Column(Integer, nullable=False, index=True)
    form_name      = Column(String(100), nullable=False)
    expected_count = Column(Integer, nullable=False, default=1)

    # FDR-derived metadata
    confidence    = Column(String(50),  nullable=True,  default=None)
    trigger_line  = Column(String(200), nullable=True,  default=None)
    trigger_value = Column(String(500), nullable=True,  default=None)
    # source: "fdr_derived" = written by FDR engine; "manual" = added by CPA
    source        = Column(String(50),  nullable=False, default="manual")

    # Fix 4a: "filing_form" = filed with IRS; "source_document" = collected from client
    document_class = Column(String(50), nullable=False, default="filing_form")

    # Fix 5: flag when FDR ran on data with blocking/critical exceptions
    derived_from_unverified_data = Column(String(5), nullable=False, default="false")

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("client_id", "tax_year", "form_name", name="uq_ledger_doc_checklist"),
        Index("ix_ledger_doc_checklist_client_year", "client_id", "tax_year"),
    )


class ClientChecklistQuestion(Base):
    """
    Fix 6b: Structured ask_client questions emitted by FDR Layer 6 (Tier 2 Resolver).
    Stores one question per ambiguous income source (e.g. line_8 other income)
    until the CPA answers it via POST .../answer-question.
    """
    __tablename__ = "client_checklist_questions"

    id            = Column(String,  primary_key=True, default=_uuid)
    client_id     = Column(String,  nullable=False, index=True)
    tax_year      = Column(Integer, nullable=False)
    question_id   = Column(String(100), nullable=False)   # e.g. "line8_income_source"
    trigger_line  = Column(String(200), nullable=True)
    trigger_value = Column(String(500), nullable=True)
    question_text = Column(Text,    nullable=False)
    options_json  = Column(JSON,    nullable=False)        # List[{label, resolves_to}]
    # status: "pending_client_response" | "resolved"
    status          = Column(String(50),  nullable=False, default="pending_client_response")
    selected_option = Column(String(200), nullable=True)
    resolved_forms  = Column(JSON,        nullable=True)   # forms added when resolved

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("client_id", "tax_year", "question_id",
                         name="uq_checklist_question"),
        Index("ix_checklist_question_client_year", "client_id", "tax_year"),
    )


class DocumentLog(Base):
    __tablename__ = "document_logs"
    id = Column(Integer, primary_key=True)
    document_id = Column(String)
    version = Column(Integer)
    upload_count = Column(Integer, default=1)
    content_hash = Column(String)
    client_id   = Column(String, nullable=True)   # FK → clients.id (cross-db reference)
    client_name = Column(String)
    document_type = Column(String)
    provider = Column(String)
    description = Column(Text)
    source = Column(String)
    tax_year = Column(Integer)
    stage = Column(String)
    status = Column(String)
    extraction_json_path = Column(String, nullable=True)  # relative path to local_extraction/<id>.json
    cpa = Column(String)
    due_date = Column(String)
    confidence_score = Column(Float)
