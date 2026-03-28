"""
backend/fdr/checklist_writer.py  —  Layer 7: Checklist Writer

Persists FDR-derived entries into client_document_checklist (ledger DB).

Merge behaviour:
  - FDR output NEVER overwrites a row where source = "manual"
  - FDR adds a new row if the form is not yet in the checklist
  - FDR updates confidence/trigger/document_class on existing FDR-originated rows
  - The source column ("fdr_derived" | "manual") is the guard

The table and columns are created by the migration in ledger/database.py.
"""
from __future__ import annotations

import logging
import uuid
from typing import List

from sqlalchemy.orm import Session

from backend.ledger.models import ClientDocumentChecklist, ClientChecklistQuestion
from backend.fdr.tier1_resolver import ChecklistEntry

log = logging.getLogger("Taxscio.fdr.checklist_writer")

# ── Fix 4b: document_class classification map ────────────────────────────────
# source_document = issued TO the taxpayer; CPA collects from client
# filing_form     = filed WITH the IRS by the taxpayer
_SOURCE_DOCUMENT_FORMS: set[str] = {
    "W-2", "1099-INT", "1099-DIV", "1099-B", "1099-NEC", "1099-MISC", "1099-K",
    "1099-R", "1099-G", "1099-S", "1099-SA", "1099-DA", "1095-A", "SSA-1099",
    "K-1 (1065)", "K-1 (1120S)", "K-1 (1041)",
}


def _norm(form_name: str) -> str:
    return (form_name or "").strip().upper()


# Pre-built normalised lookup for O(1) classification
_SOURCE_DOCUMENT_FORMS_NORM: frozenset[str] = frozenset(_norm(f) for f in _SOURCE_DOCUMENT_FORMS)


def _document_class(form_name: str) -> str:
    """Return 'source_document' or 'filing_form' for a given form name."""
    return "source_document" if _norm(form_name) in _SOURCE_DOCUMENT_FORMS_NORM else "filing_form"


def write(
    db:             Session,
    client_id:      str,
    tax_year:       int,
    entries:        List[ChecklistEntry],
    unverified_data: bool = False,
) -> int:
    """
    Upsert FDR-derived checklist entries for a client/year into the ledger DB.

    Args:
        db:               SQLAlchemy session (ledger DB).
        client_id:        UUID string of the client.
        tax_year:         Integer tax year.
        entries:          List of ChecklistEntry from the FDR engine.
        unverified_data:  True when FDR ran on data that has blocking/critical
                          exceptions (Fix 5). Marks every written row with
                          derived_from_unverified_data = "true".

    Returns:
        Number of rows written (inserted or updated).
    """
    written = 0
    unverified_str = "true" if unverified_data else "false"

    for entry in entries:
        norm_name = _norm(entry.form_name)
        if not norm_name:
            continue

        doc_class = _document_class(norm_name)

        row = (
            db.query(ClientDocumentChecklist)
            .filter(
                ClientDocumentChecklist.client_id == client_id,
                ClientDocumentChecklist.tax_year  == tax_year,
                ClientDocumentChecklist.form_name == norm_name,
            )
            .first()
        )

        if row is not None:
            # Never overwrite CPA-manually-added rows
            if getattr(row, "source", "manual") == "manual":
                log.debug("Skipping FDR write for %s — row is manually managed", norm_name)
                continue

            # Update existing FDR row
            row.confidence    = entry.confidence
            row.trigger_line  = entry.trigger_line
            row.trigger_value = entry.trigger_value
            row.document_class = doc_class
            row.derived_from_unverified_data = unverified_str
            written += 1
            log.debug("Updated FDR row: %s confidence=%s class=%s", norm_name, entry.confidence, doc_class)

        else:
            row = ClientDocumentChecklist(
                id=str(uuid.uuid4()),
                client_id=client_id,
                tax_year=tax_year,
                form_name=norm_name,
                expected_count=1,
                confidence=entry.confidence,
                trigger_line=entry.trigger_line,
                trigger_value=entry.trigger_value,
                source="fdr_derived",
                document_class=doc_class,
                derived_from_unverified_data=unverified_str,
            )
            db.add(row)
            written += 1
            log.debug("Inserted FDR row: %s confidence=%s class=%s", norm_name, entry.confidence, doc_class)

    db.commit()
    log.info(
        "Checklist write complete: client=%s year=%s rows_written=%d unverified=%s",
        client_id, tax_year, written, unverified_str,
    )
    return written


def write_questions(
    db:        Session,
    client_id: str,
    tax_year:  int,
    questions: List[dict],
) -> int:
    """
    Upsert structured ask_client questions from FDR Layer 6 (Fix 6b).

    Each question dict must have:
      question_id, trigger_line, trigger_value, question, options

    Existing pending questions are left unchanged (idempotent on question_id).
    Resolved questions are never overwritten.
    """
    written = 0
    for q in questions:
        qid = q.get("question_id", "")
        if not qid:
            continue

        existing = (
            db.query(ClientChecklistQuestion)
            .filter(
                ClientChecklistQuestion.client_id  == client_id,
                ClientChecklistQuestion.tax_year   == tax_year,
                ClientChecklistQuestion.question_id == qid,
            )
            .first()
        )
        if existing is not None:
            # Never overwrite a resolved question; re-open pending ones if data changed
            if existing.status == "resolved":
                continue
            existing.trigger_value = q.get("trigger_value")
            existing.question_text = q.get("question", existing.question_text)
            existing.options_json  = q.get("options", existing.options_json)
        else:
            row = ClientChecklistQuestion(
                id=str(uuid.uuid4()),
                client_id=client_id,
                tax_year=tax_year,
                question_id=qid,
                trigger_line=q.get("trigger_line"),
                trigger_value=q.get("trigger_value"),
                question_text=q.get("question", ""),
                options_json=q.get("options", []),
                status="pending_client_response",
            )
            db.add(row)
            written += 1

    db.commit()
    log.info(
        "Questions write complete: client=%s year=%s written=%d",
        client_id, tax_year, written,
    )
    return written
