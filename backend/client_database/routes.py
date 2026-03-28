"""
client_database/routes.py
FastAPI router exposing:
  GET  /enums/{enum_type}   → dropdown values for a given type
  GET  /enums/all           → all enum values grouped by type
  POST /clients             → create a new client record
  GET  /clients             → list clients (pagination)
"""
from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .database import get_db
from backend.ledger.database import SessionLocal as LedgerSessionLocal


def get_ledger_db():
    """FastAPI dependency that yields a ledger DB session."""
    if LedgerSessionLocal is None:
        yield None
        return
    db = LedgerSessionLocal()
    try:
        yield db
    finally:
        db.close()
from .schemas import (
    EnumItem,
    AllEnumsResponse,
    ClientCreate,
    ClientOut,
    ChecklistFormAction,
    ChecklistFormsResponse,
    DeriveFrom1040Request,
    DeriveFrom1040Response,
)
from . import services

router = APIRouter(tags=["Client Database"])


# ─────────────────────────────────────────────────────────────
# Enum routes
# ─────────────────────────────────────────────────────────────
@router.get("/enums/all", response_model=AllEnumsResponse, summary="All enums grouped by type")
def get_all_enums(
    tenant_id: Optional[str] = Query(None, description="Tenant UUID (optional)"),
    db: Session = Depends(get_db),
):
    grouped = services.get_all_enums(db, tenant_id=tenant_id)
    return AllEnumsResponse(
        enums={
            k: [EnumItem(code=e.code, label=e.label, color=e.color) for e in v]
            for k, v in grouped.items()
        }
    )


@router.get("/enums/{enum_type}", response_model=List[EnumItem], summary="Enum values for a type")
def get_enum(
    enum_type: str,
    tenant_id: Optional[str] = Query(None, description="Tenant UUID (optional)"),
    db: Session = Depends(get_db),
):
    rows = services.get_enums_by_type(db, enum_type=enum_type, tenant_id=tenant_id)
    return [EnumItem(code=r.code, label=r.label, color=r.color) for r in rows]


# ─────────────────────────────────────────────────────────────
# Client routes
# ─────────────────────────────────────────────────────────────
@router.post("/clients", response_model=ClientOut, status_code=201, summary="Create a new client")
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
):
    try:
        client = services.create_client(db, payload)
        return client
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/clients", response_model=List[ClientOut], summary="List clients")
def list_clients(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return services.list_clients(db, limit=limit, offset=offset)


@router.get(
    "/clients/{client_id}/document-checklist",
    response_model=ChecklistFormsResponse,
    summary="Client document checklist for tax year",
)
def get_document_checklist(
    client_id: str,
    tax_year: Optional[int] = Query(None, description="Target tax year"),
    db: Session = Depends(get_db),
    ldb: Session = Depends(get_ledger_db),
):
    try:
        return services.get_client_document_checklist(db, client_id=client_id, tax_year=tax_year, ldb=ldb)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/clients/{client_id}/document-checklist/forms",
    response_model=ChecklistFormsResponse,
    summary="Add or increment checklist form",
)
def add_document_checklist_form(
    client_id: str,
    payload: ChecklistFormAction,
    tax_year: Optional[int] = Query(None, description="Target tax year"),
    db: Session = Depends(get_db),
    ldb: Session = Depends(get_ledger_db),
):
    services.increment_checklist_form(
        db,
        client_id=client_id,
        form_name=payload.form_name,
        tax_year=tax_year,
        ldb=ldb,
    )
    return services.get_client_document_checklist(db, client_id=client_id, tax_year=tax_year, ldb=ldb)


@router.delete(
    "/clients/{client_id}/document-checklist/forms/{form_name}",
    response_model=ChecklistFormsResponse,
    summary="Decrement or remove checklist form",
)
def remove_document_checklist_form(
    client_id: str,
    form_name: str,
    tax_year: Optional[int] = Query(None, description="Target tax year"),
    db: Session = Depends(get_db),
    ldb: Session = Depends(get_ledger_db),
):
    services.decrement_checklist_form(
        db,
        client_id=client_id,
        form_name=form_name,
        tax_year=tax_year,
        ldb=ldb,
    )
    return services.get_client_document_checklist(db, client_id=client_id, tax_year=tax_year, ldb=ldb)


@router.post(
    "/clients/{client_id}/document-checklist/derive-from-1040",
    response_model=DeriveFrom1040Response,
    status_code=200,
    summary="Run FDR on extracted 1040 JSON and populate the document checklist",
    description=(
        "Accepts the extracted 1040 JSON and per-field confidence map returned by /extract. "
        "Runs all 7 FDR layers (pre-pass validator, tax year router, null classifier, "
        "Tier 1 resolver, conflict resolver, Tier 2 resolver, checklist writer) and writes "
        "results to client_document_checklist. "
        "FDR output never overwrites manually-added (CPA) checklist rows."
    ),
)
def derive_checklist_from_1040(
    client_id: str,
    payload:   DeriveFrom1040Request,
    db: Session = Depends(get_db),
    ldb: Session = Depends(get_ledger_db),
):
    try:
        result = services.derive_from_1040(
            db=db,
            client_id=client_id,
            tax_year=payload.tax_year,
            extracted_fields=payload.extracted_fields,
            field_confidence_map=payload.field_confidence_map,
            document_type=payload.document_type,
            ldb=ldb,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"FDR engine error: {exc}")
