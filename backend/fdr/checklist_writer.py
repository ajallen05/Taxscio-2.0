"""
backend/fdr/checklist_writer.py  —  Layer 7: Checklist Writer

Persists FDR-derived entries into client_document_checklist (ledger DB).

Merge behaviour:
  - FDR output NEVER overwrites a row where source = "manual"
  - FDR adds a new row if the form is not yet in the checklist
  - FDR updates confidence/trigger on existing FDR-originated rows
  - The source column ("fdr_derived" | "manual") is the guard

The table and columns are created by the migration in ledger/database.py.
"""
from __future__ import annotations

import logging
import uuid
from typing import List

from sqlalchemy.orm import Session

from backend.ledger.models import ClientDocumentChecklist
from backend.fdr.tier1_resolver import ChecklistEntry

log = logging.getLogger("Taxscio.fdr.checklist_writer")


def _norm(form_name: str) -> str:
    return (form_name or "").strip().upper()


def write(
    db:          Session,
    client_id:   str,
    tax_year:    int,
    entries:     List[ChecklistEntry],
) -> int:
    """
    Upsert FDR-derived checklist entries for a client/year.

    Args:
        db:        SQLAlchemy session (client_database).
        client_id: UUID string of the client.
        tax_year:  Integer tax year.
        entries:   List of ChecklistEntry from the FDR engine.

    Returns:
        Number of rows written (inserted or updated).
    """
    written = 0

    for entry in entries:
        norm_name = _norm(entry.form_name)
        if not norm_name:
            continue

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
                log.debug(
                    "Skipping FDR write for %s — row is manually managed", norm_name
                )
                continue

            # Update existing FDR row
            row.confidence   = entry.confidence
            row.trigger_line = entry.trigger_line
            row.trigger_value = entry.trigger_value
            written += 1
            log.debug("Updated FDR row: %s confidence=%s", norm_name, entry.confidence)

        else:
            # Insert new FDR-derived row
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
            )
            db.add(row)
            written += 1
            log.debug("Inserted FDR row: %s confidence=%s", norm_name, entry.confidence)

    db.commit()
    log.info(
        "Checklist write complete: client=%s year=%s rows_written=%d",
        client_id, tax_year, written,
    )
    return written
