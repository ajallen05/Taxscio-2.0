"""
client_database/models.py
SQLAlchemy ORM models for the two core tables:
  - enum_master              (drives all dropdowns)
  - clients                  (stores client records)
  - client_document_checklist (expected documents per client/year)
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, Date, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from .database import Base


def _now():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────
# TABLE 1: enum_master
# ─────────────────────────────────────────────────────────────
class EnumMaster(Base):
    __tablename__ = "enum_master"

    id          = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    enum_type   = Column(String(100), nullable=False, index=True)
    code        = Column(String(100), nullable=False)
    label       = Column(String(255), nullable=False)
    description = Column(Text,        nullable=True)
    sort_order  = Column(Integer,     nullable=False, default=0)
    color       = Column(String(50),  nullable=True)
    is_active   = Column(Boolean,     nullable=False, default=True)
    is_system   = Column(Boolean,     nullable=False, default=False)
    tenant_id   = Column(UUID(as_uuid=False), nullable=True, default=None)
    created_at  = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at  = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_enum_master_enum_type_code", "enum_type", "code"),
        UniqueConstraint("enum_type", "code", name="uq_enum_master_type_code"),
    )


# ─────────────────────────────────────────────────────────────
# TABLE 2: clients
# ─────────────────────────────────────────────────────────────
class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)

    # ── Entity Info ──────────────────────────────────────────
    entity_type          = Column(String(20),  nullable=False)
    first_name           = Column(String(100), nullable=True)
    last_name            = Column(String(100), nullable=True)
    business_name        = Column(String(255), nullable=True)
    trust_name           = Column(String(255), nullable=True)
    date_of_birth        = Column(Date,        nullable=True)
    date_of_incorporation= Column(Date,        nullable=True)

    # ── Contact ──────────────────────────────────────────────
    email = Column(String(150), nullable=True, index=True)
    phone = Column(String(20),  nullable=True)

    # ── Tax Info ─────────────────────────────────────────────
    tax_id           = Column(String(50),  nullable=True)
    country          = Column(String(100), nullable=True)
    residency_status = Column(String(50),  nullable=True)

    # ── Address ──────────────────────────────────────────────
    address_line1 = Column(Text,         nullable=True)
    address_line2 = Column(Text,         nullable=True)
    city          = Column(String(100),  nullable=True)
    state         = Column(String(100),  nullable=True)
    zip_code      = Column(String(20),   nullable=True)

    # ── Classification ───────────────────────────────────────
    lifecycle_stage = Column(String(50),  nullable=True)
    risk_profile    = Column(String(50),  nullable=True)
    source          = Column(String(100), nullable=True)

    # ── Additional ───────────────────────────────────────────
    notes = Column(Text, nullable=True)
    tags  = Column(JSONB, nullable=True, default=list)

    # ── Audit ────────────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_clients_email", "email"),
        Index("ix_clients_entity_type", "entity_type"),
        Index("ix_clients_lifecycle_stage", "lifecycle_stage"),
    )


class ClientDocumentChecklist(Base):
    __tablename__ = "client_document_checklist"

    id             = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    client_id      = Column(UUID(as_uuid=False), nullable=False, index=True)
    tax_year       = Column(Integer,     nullable=False, index=True)
    form_name      = Column(String(100), nullable=False)
    expected_count = Column(Integer,     nullable=False, default=1)

    # ── FDR-derived metadata (added by Form Dependency Resolver) ─────────────
    # confidence   : "deterministic" | "inferred" | "unresolvable" | NULL (manual)
    # trigger_line : flat field name that caused this form to be flagged
    # trigger_value: string value of that field at the time FDR ran
    # source       : "fdr_derived" = written by FDR; "manual" = added by CPA
    #                FDR never overwrites rows where source = "manual"
    confidence    = Column(String(50),  nullable=True,  default=None)
    trigger_line  = Column(String(200), nullable=True,  default=None)
    trigger_value = Column(String(500), nullable=True,  default=None)
    source        = Column(String(50),  nullable=False, default="manual")

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("client_id", "tax_year", "form_name", name="uq_client_doc_checklist"),
        Index("ix_client_doc_checklist_client_year", "client_id", "tax_year"),
    )
