"""
client_database/services.py
Business logic for enum and client operations.
"""
from __future__ import annotations
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from .models import EnumMaster, Client
from .schemas import ClientCreate


# ─────────────────────────────────────────────────────────────
# Enum services
# ─────────────────────────────────────────────────────────────
def get_enums_by_type(
    db: Session,
    enum_type: str,
    tenant_id: Optional[str] = None,
) -> List[EnumMaster]:
    """Return active enum entries for a given type, global + tenant-scoped."""
    q = db.query(EnumMaster).filter(
        EnumMaster.enum_type == enum_type,
        EnumMaster.is_active == True,
    )
    if tenant_id:
        q = q.filter(
            (EnumMaster.tenant_id == None) | (EnumMaster.tenant_id == tenant_id)
        )
    else:
        q = q.filter(EnumMaster.tenant_id == None)
    return q.order_by(EnumMaster.sort_order).all()


def get_all_enums(
    db: Session,
    tenant_id: Optional[str] = None,
) -> Dict[str, List[EnumMaster]]:
    """Return all active enums grouped by enum_type."""
    q = db.query(EnumMaster).filter(EnumMaster.is_active == True)
    if tenant_id:
        q = q.filter(
            (EnumMaster.tenant_id == None) | (EnumMaster.tenant_id == tenant_id)
        )
    else:
        q = q.filter(EnumMaster.tenant_id == None)
    rows = q.order_by(EnumMaster.enum_type, EnumMaster.sort_order).all()
    grouped: Dict[str, List[EnumMaster]] = {}
    for row in rows:
        grouped.setdefault(row.enum_type, []).append(row)
    return grouped


def validate_enum_code(db: Session, enum_type: str, code: str) -> bool:
    """Check that an enum code is valid and active."""
    if code is None:
        return True  # optional fields are ok
    return db.query(EnumMaster).filter(
        EnumMaster.enum_type == enum_type,
        EnumMaster.code == code,
        EnumMaster.is_active == True,
    ).first() is not None


# ─────────────────────────────────────────────────────────────
# Client services
# ─────────────────────────────────────────────────────────────
_ENUM_FIELDS = {
    "entity_type":       "entity_type",
    "country":           "country",
    "residency_status":  "residency_status",
    "state":             "state",
    "lifecycle_stage":   "lifecycle_stage",
    "risk_profile":      "risk_profile",
    "source":            "source",
}


def create_client(db: Session, payload: ClientCreate) -> Client:
    """
    Validate enum codes, then persist and return a new Client row.
    Raises ValueError for invalid enum codes.
    """
    # Validate all enum-backed fields
    for field, enum_type in _ENUM_FIELDS.items():
        val = getattr(payload, field, None)
        if val and not validate_enum_code(db, enum_type, val):
            raise ValueError(
                f"Invalid value '{val}' for field '{field}'. "
                f"Not found in enum_master[{enum_type}]."
            )

    client = Client(
        id=str(uuid.uuid4()),
        entity_type=payload.entity_type,
        first_name=payload.first_name,
        last_name=payload.last_name,
        business_name=payload.business_name,
        trust_name=payload.trust_name,
        date_of_birth=payload.date_of_birth,
        date_of_incorporation=payload.date_of_incorporation,
        email=payload.email,
        phone=payload.phone,
        tax_id=payload.tax_id,
        country=payload.country,
        residency_status=payload.residency_status,
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        city=payload.city,
        state=payload.state,
        zip_code=payload.zip_code,
        lifecycle_stage=payload.lifecycle_stage,
        risk_profile=payload.risk_profile,
        source=payload.source,
        notes=payload.notes,
        tags=payload.tags or [],
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def list_clients(db: Session, limit: int = 100, offset: int = 0) -> List[Client]:
    return db.query(Client).order_by(Client.created_at.desc()).offset(offset).limit(limit).all()
