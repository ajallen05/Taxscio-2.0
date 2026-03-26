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
from .schemas import EnumItem, AllEnumsResponse, ClientCreate, ClientOut
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
