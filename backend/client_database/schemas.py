"""
client_database/schemas.py
Pydantic schemas for request/response validation.
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, field_validator, model_validator


# ─────────────────────────────────────────────────────────────
# Enum schemas
# ─────────────────────────────────────────────────────────────
class EnumItem(BaseModel):
    code:  str
    label: str
    color: Optional[str] = None

    model_config = {"from_attributes": True}


class AllEnumsResponse(BaseModel):
    enums: dict[str, List[EnumItem]]


# ─────────────────────────────────────────────────────────────
# Client schemas
# ─────────────────────────────────────────────────────────────
class ClientCreate(BaseModel):
    # Entity
    entity_type:           str
    first_name:            Optional[str] = None
    last_name:             Optional[str] = None
    business_name:         Optional[str] = None
    trust_name:            Optional[str] = None
    date_of_birth:         Optional[date] = None
    date_of_incorporation: Optional[date] = None

    # Contact
    email: Optional[str] = None
    phone: Optional[str] = None

    # Tax
    tax_id:           Optional[str] = None
    country:          Optional[str] = None
    residency_status: Optional[str] = None

    # Address
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city:          Optional[str] = None
    state:         Optional[str] = None
    zip_code:      Optional[str] = None

    # Classification
    lifecycle_stage: Optional[str] = None
    risk_profile:    Optional[str] = None
    source:          Optional[str] = None

    # Additional
    notes: Optional[str] = None
    tags:  Optional[List[str]] = None

    @model_validator(mode="after")
    def validate_entity_fields(self) -> "ClientCreate":
        et = (self.entity_type or "").upper()
        if et == "INDIVIDUAL":
            if not self.first_name:
                raise ValueError("first_name is required for INDIVIDUAL entity type")
            if not self.last_name:
                raise ValueError("last_name is required for INDIVIDUAL entity type")
        elif et == "BUSINESS":
            if not self.business_name:
                raise ValueError("business_name is required for BUSINESS entity type")
        elif et == "TRUST":
            if not self.trust_name:
                raise ValueError("trust_name is required for TRUST entity type")
        return self


class ClientOut(BaseModel):
    id:                    str
    entity_type:           str
    first_name:            Optional[str]
    last_name:             Optional[str]
    business_name:         Optional[str]
    trust_name:            Optional[str]
    date_of_birth:         Optional[date]
    date_of_incorporation: Optional[date]
    email:                 Optional[str]
    phone:                 Optional[str]
    tax_id:                Optional[str]
    country:               Optional[str]
    residency_status:      Optional[str]
    address_line1:         Optional[str]
    address_line2:         Optional[str]
    city:                  Optional[str]
    state:                 Optional[str]
    zip_code:              Optional[str]
    lifecycle_stage:       Optional[str]
    risk_profile:          Optional[str]
    source:                Optional[str]
    notes:                 Optional[str]
    tags:                  Optional[List[str]]
    created_at:            datetime
    updated_at:            datetime

    model_config = {"from_attributes": True}


class ChecklistFormItem(BaseModel):
    form_name:        str
    count:            int
    submitted_count:  int
    prior_year_count: int = 0          # how many were submitted in the previous tax year
    status:           str
    # FDR-derived metadata (null for manually-added rows)
    confidence:    Optional[str] = None  # "deterministic" | "inferred" | "unresolvable"
    trigger_line:  Optional[str] = None  # flat field that caused this flag
    trigger_value: Optional[str] = None  # value of that field at FDR run time
    source:        Optional[str] = None  # "fdr_derived" | "manual"


class ChecklistFormsResponse(BaseModel):
    tax_year:      int
    previous_year: Optional[int] = None
    forms:         List[ChecklistFormItem]


class ChecklistFormAction(BaseModel):
    form_name: str


# ─────────────────────────────────────────────────────────────
# FDR derive-from-1040 endpoint schemas
# ─────────────────────────────────────────────────────────────

class DeriveFrom1040Request(BaseModel):
    tax_year:           int
    extracted_fields:   Dict[str, Any]        # full nested 1040 JSON from /extract
    field_confidence_map: Dict[str, float]    # per-field scores from scorer.py
    document_type:      Literal["digital", "scanned"] = "digital"
    session_id:         Optional[str] = None  # optional audit trail reference


class FDRSummary(BaseModel):
    deterministic_count:   int
    inferred_count:        int
    unresolvable_count:    int
    conflicts_detected:    List[str]
    pre_pass_flags:        List[str]
    tax_year_rules_loaded: str


class DeriveFrom1040Response(BaseModel):
    forms:       List[ChecklistFormItem]
    fdr_summary: FDRSummary
