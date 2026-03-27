"""
backend/fdr/fdr_engine.py  —  Form Dependency Resolver Orchestrator

Runs all 7 layers in sequence and (optionally) writes results to the DB.

Call from:
  1. POST /clients/{id}/document-checklist/derive-from-1040  (explicit endpoint)
  2. POST /extract (when client_id is present in context)    (implicit auto-trigger)

The FDR is additive and non-blocking.  If it fails at any layer, the failure
is logged but does NOT affect the extraction response.

Architecture:
  Layer 1  pre_pass_validator    — mark impossible fields as unreliable
  Layer 2  tax_year_router       — load year-specific rule file
  Layer 3  null_classifier       — classify null fields (blank vs unreadable)
  Layer 4  tier1_resolver        — evaluate rules against reliable fields
  Layer 5  conflict_resolver     — cross-form consistency checks
  Layer 6  tier2_resolver        — conditional + unconditional ask_client items
  Layer 7  checklist_writer      — upsert results to client_document_checklist
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.utils.data import flatten_for_validation
from backend.fdr import pre_pass_validator
from backend.fdr import tax_year_router
from backend.fdr import null_classifier
from backend.fdr import tier1_resolver
from backend.fdr import conflict_resolver
from backend.fdr import tier2_resolver
from backend.fdr import checklist_writer
from backend.fdr.tier1_resolver import ChecklistEntry

log = logging.getLogger("Taxscio.fdr.engine")


def run(
    extracted_json:    Dict[str, Any],
    confidence_map:    Dict[str, float],
    doc_type:          str,
    tax_year:          Optional[int],
    client_id:         Optional[str] = None,
    db=None,
) -> Dict[str, Any]:
    """
    Run the full 7-layer FDR pipeline.

    Args:
        extracted_json:  Nested 1040 JSON as returned by NuExtract normalizer.
        confidence_map:  Per-field confidence scores from scorer.py
                         (field_confidence dict from integrity_data).
        doc_type:        "digital" or "scanned" — from gate_result["pdf_type"].
        tax_year:        Tax year from the extracted JSON or context.
                         Pass None to auto-detect from extracted_json["tax_year"].
        client_id:       If provided + db provided, writes results to DB.
        db:              SQLAlchemy Session for client_database.
                         If None, results are returned but not persisted.

    Returns:
        {
          "entries":     [ChecklistEntry, ...],
          "fdr_summary": {
              "deterministic_count":   int,
              "inferred_count":        int,
              "unresolvable_count":    int,
              "conflicts_detected":    [str, ...],
              "pre_pass_flags":        [str, ...],
              "tax_year_rules_loaded": str,
          }
        }
    """
    # ── Resolve tax year ────────────────────────────────────────────────────
    if tax_year is None:
        tax_year = extracted_json.get("tax_year")
    if tax_year is not None:
        try:
            tax_year = int(tax_year)
        except (ValueError, TypeError):
            tax_year = None

    # ── Normalize doc_type ──────────────────────────────────────────────────
    doc_type = (doc_type or "digital").lower()
    if doc_type not in ("digital", "scanned"):
        doc_type = "digital"

    log.info(
        "FDR start: client=%s year=%s doc_type=%s",
        client_id or "—", tax_year or "—", doc_type,
    )

    # ── Layer 1: Pre-Pass Validator ─────────────────────────────────────────
    flat_data = flatten_for_validation(extracted_json)
    reliability_map, pre_flags = pre_pass_validator.run(flat_data)
    pre_pass_notes = [f.reason for f in pre_flags]

    # ── Layer 2: Tax Year Router ────────────────────────────────────────────
    rules, year_label = tax_year_router.load_rules(tax_year)

    # ── Layer 3: Null Ambiguity Classifier ──────────────────────────────────
    null_map = null_classifier.build_null_map(flat_data, confidence_map, doc_type)

    # ── Layer 4: Tier 1 Resolver ─────────────────────────────────────────────
    tier1_entries = tier1_resolver.run(
        flat_data=flat_data,
        raw_data=extracted_json,
        rules=rules,
        reliability_map=reliability_map,
        null_map=null_map,
    )

    # ── Layer 5: Conflict Resolver ───────────────────────────────────────────
    resolved_entries, conflict_notes = conflict_resolver.run(
        entries=tier1_entries,
        flat_data=flat_data,
        raw_data=extracted_json,
        tax_year=tax_year or 2026,
    )

    # ── Layer 6: Tier 2 Resolver ─────────────────────────────────────────────
    final_entries = tier2_resolver.run(
        tier1_entries=resolved_entries,
        flat_data=flat_data,
        null_map=null_map,
        tax_year=tax_year or 2026,
    )

    # ── Layer 7: Checklist Writer ────────────────────────────────────────────
    if client_id and db is not None and tax_year:
        try:
            checklist_writer.write(
                db=db,
                client_id=client_id,
                tax_year=tax_year,
                entries=final_entries,
            )
        except Exception as exc:
            log.error("Checklist write failed (non-fatal): %s", exc)

    # ── Build summary ─────────────────────────────────────────────────────────
    det   = sum(1 for e in final_entries if e.confidence == "deterministic")
    inf   = sum(1 for e in final_entries if e.confidence == "inferred")
    unres = sum(1 for e in final_entries if e.confidence == "unresolvable")

    log.info(
        "FDR complete: deterministic=%d inferred=%d unresolvable=%d conflicts=%d",
        det, inf, unres, len(conflict_notes),
    )

    return {
        "entries": final_entries,
        "fdr_summary": {
            "deterministic_count":   det,
            "inferred_count":        inf,
            "unresolvable_count":    unres,
            "conflicts_detected":    conflict_notes,
            "pre_pass_flags":        pre_pass_notes,
            "tax_year_rules_loaded": year_label,
        },
    }
