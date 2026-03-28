"""
client_database/services.py
Business logic for enum and client operations.
"""
from __future__ import annotations
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from backend.ledger.database import SessionLocal as LedgerSessionLocal
from backend.ledger.models import Ledger, ClientDocumentChecklist
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


def get_client_display_name(client: Client) -> str:
    et = (client.entity_type or "").upper()
    if et == "INDIVIDUAL":
        name = f"{client.first_name or ''} {client.last_name or ''}".strip()
        if name:
            return name
    return (
        (client.business_name or "").strip()
        or (client.trust_name or "").strip()
        or f"{client.first_name or ''} {client.last_name or ''}".strip()
        or "Unknown"
    )


def _derive_status(expected_count: int, submitted_count: int, has_error: bool) -> str:
    if has_error:
        return "Error"
    if submitted_count <= 0:
        return "Pending"
    if submitted_count < expected_count:
        return "Partial"
    return "Received"


def _norm_form_name(form_name: str) -> str:
    return (form_name or "").strip().upper()


def _current_tax_year() -> int:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).year


# Forms that are the return itself — never shown as items to collect in the checklist.
_CHECKLIST_EXCLUDED_FORMS: set[str] = {
    "1040", "1040-SR", "1040-NR", "1040-NR-EZ",
    "1040-X", "1040-ES", "1040-V",
}


def get_client_document_checklist(
    db: Session,
    client_id: str,
    tax_year: Optional[int] = None,
    ldb: Optional[Session] = None,
) -> Dict[str, Any]:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise ValueError("Client not found")

    target_year = int(tax_year) if tax_year else _current_tax_year()
    previous_year = target_year - 1
    form_counts: Dict[str, int] = {}
    submitted_counts: Dict[str, int] = {}
    prior_year_counts: Dict[str, int] = {}
    has_error: Dict[str, bool] = {}

    # Checklist rows live in the ledger DB; open a session if one wasn't passed in.
    _close_ldb = False
    if ldb is None and LedgerSessionLocal is not None:
        ldb = LedgerSessionLocal()
        _close_ldb = True

    rows = []
    if ldb is not None:
        try:
            rows = ldb.query(ClientDocumentChecklist).filter(
                ClientDocumentChecklist.client_id == client_id,
                ClientDocumentChecklist.tax_year == target_year,
            ).all()
        except Exception:
            pass
        finally:
            if _close_ldb:
                ldb.close()
                ldb = None
    for row in rows:
        key = _norm_form_name(row.form_name)
        if key in _CHECKLIST_EXCLUDED_FORMS:
            continue
        form_counts[key] = max(1, int(row.expected_count or 1))

    # Seed from ledger: prior year gives hints; current year gives submission status.
    client_name = get_client_display_name(client)
    if LedgerSessionLocal is not None:
        ldb = LedgerSessionLocal()
        try:
            # Build ledger filter: prefer client_id match; fall back to name for legacy rows.
            def _ledger_filter(year):
                by_id   = ldb.query(Ledger).filter(
                    Ledger.client_id == str(client_id),
                    Ledger.tax_year  == year,
                ).all()
                if by_id:
                    return by_id
                # Fallback: name-based for records predating the client_id column
                return ldb.query(Ledger).filter(
                    Ledger.client_name == client_name,
                    Ledger.client_id.is_(None),
                    Ledger.tax_year == year,
                ).all()

            # Prior-year docs — seed into checklist AND record prior-year counts for comparison.
            prev_docs = _ledger_filter(previous_year)
            for rec in prev_docs:
                key = _norm_form_name(rec.document_type or "")
                if not key or key in _CHECKLIST_EXCLUDED_FORMS:
                    continue
                prior_year_counts[key] = prior_year_counts.get(key, 0) + int(rec.upload_count or 1)
                # Seed into current-year checklist only if not already present.
                form_counts.setdefault(key, 1)

            # Current-year docs — track what the client has already submitted this year.
            current_docs = _ledger_filter(target_year)
            for rec in current_docs:
                key = _norm_form_name(rec.document_type or "")
                if not key or key in _CHECKLIST_EXCLUDED_FORMS:
                    continue
                submitted_counts[key] = submitted_counts.get(key, 0) + int(rec.upload_count or 1)
                raw = (rec.status or "").upper()
                has_error[key] = has_error.get(key, False) or raw in {"ERROR", "FAILED", "REJECTED"}
                form_counts.setdefault(key, 1)
        finally:
            ldb.close()

    # Build FDR metadata map from checklist rows.
    fdr_meta: Dict[str, Dict] = {}
    for row in rows:
        key = _norm_form_name(row.form_name)
        if key in _CHECKLIST_EXCLUDED_FORMS:
            continue
        fdr_meta[key] = {
            "confidence":    getattr(row, "confidence",    None),
            "trigger_line":  getattr(row, "trigger_line",  None),
            "trigger_value": getattr(row, "trigger_value", None),
            "source":        getattr(row, "source",        "manual"),
        }

    forms = []
    for form_name in sorted(form_counts.keys()):
        count     = form_counts[form_name]
        submitted = submitted_counts.get(form_name, 0)
        meta      = fdr_meta.get(form_name, {})
        forms.append({
            "form_name":        form_name,
            "count":            count,
            "submitted_count":  submitted,
            "prior_year_count": prior_year_counts.get(form_name, 0),
            "status":           _derive_status(count, submitted, has_error.get(form_name, False)),
            "confidence":       meta.get("confidence"),
            "trigger_line":     meta.get("trigger_line"),
            "trigger_value":    meta.get("trigger_value"),
            "source":           meta.get("source", "manual"),
        })

    return {"tax_year": target_year, "forms": forms, "previous_year": previous_year}


def derive_from_1040(
    db:              "Session",
    client_id:       str,
    tax_year:        int,
    extracted_fields: Dict[str, Any],
    field_confidence_map: Dict[str, Any],
    document_type:   str,
    ldb:             Optional["Session"] = None,
) -> Dict[str, Any]:
    """
    Run the FDR engine and write results to client_document_checklist (ledger DB).

    This is the service backing POST /clients/{id}/document-checklist/derive-from-1040.

    Returns the full fdr result dict (entries + fdr_summary) AND the updated
    checklist response (same shape as get_client_document_checklist).
    """
    from backend.fdr.fdr_engine import run as fdr_run

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise ValueError("Client not found")

    # Open a ledger DB session for the checklist writer if one wasn't provided.
    _close_ldb = False
    if ldb is None and LedgerSessionLocal is not None:
        ldb = LedgerSessionLocal()
        _close_ldb = True

    try:
        result = fdr_run(
            extracted_json=extracted_fields,
            confidence_map={k: float(v) for k, v in (field_confidence_map or {}).items()},
            doc_type=document_type,
            tax_year=tax_year,
            client_id=client_id,
            db=ldb,   # FDR/checklist_writer now writes to ledger DB
        )
        checklist = get_client_document_checklist(db, client_id=client_id, tax_year=tax_year, ldb=ldb)
    finally:
        if _close_ldb and ldb is not None:
            ldb.close()

    return {
        "forms":       checklist["forms"],
        "fdr_summary": result["fdr_summary"],
    }


def increment_checklist_form(
    db: Session,
    client_id: str,
    form_name: str,
    tax_year: Optional[int] = None,
    ldb: Optional[Session] = None,
) -> None:
    """Add or increment a checklist form entry in the ledger DB."""
    target_year = int(tax_year) if tax_year else _current_tax_year()
    norm_form = _norm_form_name(form_name)
    if not norm_form:
        raise ValueError("Form name is required")

    _close_ldb = False
    if ldb is None and LedgerSessionLocal is not None:
        ldb = LedgerSessionLocal()
        _close_ldb = True
    if ldb is None:
        raise RuntimeError("Ledger DB not configured")

    try:
        row = ldb.query(ClientDocumentChecklist).filter(
            ClientDocumentChecklist.client_id == client_id,
            ClientDocumentChecklist.tax_year == target_year,
            ClientDocumentChecklist.form_name == norm_form,
        ).first()
        if row:
            row.expected_count = int(row.expected_count or 1) + 1
            row.source = "manual"
        else:
            row = ClientDocumentChecklist(
                id=str(uuid.uuid4()),
                client_id=client_id,
                tax_year=target_year,
                form_name=norm_form,
                expected_count=1,
                source="manual",
            )
            ldb.add(row)
        ldb.commit()
    finally:
        if _close_ldb:
            ldb.close()


def decrement_checklist_form(
    db: Session,
    client_id: str,
    form_name: str,
    tax_year: Optional[int] = None,
    ldb: Optional[Session] = None,
) -> None:
    """Remove or decrement a checklist form entry in the ledger DB."""
    target_year = int(tax_year) if tax_year else _current_tax_year()
    norm_form = _norm_form_name(form_name)
    if not norm_form:
        raise ValueError("Form name is required")

    _close_ldb = False
    if ldb is None and LedgerSessionLocal is not None:
        ldb = LedgerSessionLocal()
        _close_ldb = True
    if ldb is None:
        return

    try:
        row = ldb.query(ClientDocumentChecklist).filter(
            ClientDocumentChecklist.client_id == client_id,
            ClientDocumentChecklist.tax_year == target_year,
            ClientDocumentChecklist.form_name == norm_form,
        ).first()
        if not row:
            return
        next_count = int(row.expected_count or 1) - 1
        if next_count <= 0:
            ldb.delete(row)
        else:
            row.expected_count = next_count
        ldb.commit()
    finally:
        if _close_ldb:
            ldb.close()
