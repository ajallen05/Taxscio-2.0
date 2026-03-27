"""
local_extraction_store.py
─────────────────────────
Persists every extraction result to  backend/local_extraction/<document_id>.json
and keeps that file in sync whenever exceptions are updated later.

Public API
──────────
    save_extraction(document_id, form_type, source_filename, pdf_type,
                    data, exceptions, document_confidence, field_confidence, *, extra=None)

    update_exceptions(document_id, exception_audit_entry)
        → appends one escalation event and refreshes `last_updated_at`

    get_extraction(document_id) → dict | None

    list_extractions()           → list[dict]  (summary rows, no full data)
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ── Storage directory ────────────────────────────────────────────────────────
_BACKEND_DIR = Path(__file__).resolve().parent
EXTRACTION_DIR = _BACKEND_DIR / "local_extraction"


def _ensure_dir() -> None:
    EXTRACTION_DIR.mkdir(parents=True, exist_ok=True)


def _safe_id(document_id: str) -> str:
    """Strip characters that are unsafe in filenames."""
    return re.sub(r"[^\w\-]", "_", document_id)


def _path(document_id: str) -> Path:
    return EXTRACTION_DIR / f"{_safe_id(document_id)}.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Core helpers ─────────────────────────────────────────────────────────────

def _read(document_id: str) -> dict | None:
    p = _path(document_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("local_extraction_store: failed to read %s — %s", p, exc)
        return None


def _write(document_id: str, record: dict) -> None:
    _ensure_dir()
    p = _path(document_id)
    try:
        p.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
        log.debug("local_extraction_store: saved %s", p.name)
    except Exception as exc:
        log.error("local_extraction_store: failed to write %s — %s", p, exc)


# ── Public API ────────────────────────────────────────────────────────────────

def save_extraction(
    document_id: str,
    form_type: str,
    source_filename: str,
    pdf_type: str | None,
    data: dict,
    exceptions: list,
    document_confidence: float,
    field_confidence: dict | None = None,
    *,
    extra: dict | None = None,
) -> str:
    """
    Create or fully overwrite the extraction record for *document_id*.
    If the file already exists the exception_audit trail is preserved.
    Returns the relative path  ``local_extraction/<document_id>.json``
    so callers can store it in the ledger.
    """
    existing = _read(document_id) or {}
    now = _now_iso()

    record: dict[str, Any] = {
        "document_id":          document_id,
        "form_type":            form_type,
        "source_filename":      source_filename,
        "pdf_type":             pdf_type or "unknown",
        "extracted_at":         existing.get("extracted_at") or now,
        "last_updated_at":      now,
        "document_confidence":  document_confidence,
        "data":                 data,
        "exceptions":           exceptions,
        "field_confidence":     field_confidence or {},
        # preserve any escalation history
        "exception_audit":      existing.get("exception_audit") or [],
    }
    if extra:
        record.update(extra)

    _write(document_id, record)
    # Return a portable relative path (from the backend root)
    return f"local_extraction/{_safe_id(document_id)}.json"


def update_exceptions(document_id: str, exception_audit_entry: dict) -> bool:
    """
    Append one escalation event to the record's exception_audit list and
    refresh last_updated_at.  Returns True if the file was found and updated.
    """
    record = _read(document_id)
    if record is None:
        log.debug(
            "local_extraction_store: update_exceptions — no file for %s", document_id
        )
        return False

    audit: list = record.get("exception_audit") or []
    audit.append(exception_audit_entry)
    record["exception_audit"] = audit
    record["last_updated_at"] = _now_iso()
    _write(document_id, record)
    return True


def mark_exception_resolved(
    document_id: str,
    exception_code: str | None,
    exception_field: str | None,
    audit_entry: dict,
) -> bool:
    """
    Remove the matching exception from the live ``exceptions`` array AND
    append an audit entry — both in a single write.

    Matching logic:  code AND field must both match (either may be None/empty
    for a wildcard match on that dimension).
    Returns True if the file was found (even if no exception matched).
    """
    record = _read(document_id)
    if record is None:
        return False

    def _matches(exc: dict) -> bool:
        code_ok  = (not exception_code)  or exc.get("code")  == exception_code
        field_ok = (not exception_field) or exc.get("field") == exception_field
        return code_ok and field_ok

    original = record.get("exceptions") or []
    remaining = [e for e in original if not _matches(e)]
    record["exceptions"] = remaining

    audit: list = record.get("exception_audit") or []
    audit.append(audit_entry)
    record["exception_audit"] = audit
    record["last_updated_at"] = _now_iso()

    _write(document_id, record)
    log.debug(
        "local_extraction_store: resolved exception code=%s field=%s — %d → %d remaining",
        exception_code, exception_field, len(original), len(remaining),
    )
    return True


def get_extraction(document_id: str) -> dict | None:
    """Return the full extraction record, or None if not found."""
    return _read(document_id)


def list_extractions() -> list[dict]:
    """
    Return a lightweight summary list (no full data payload) of every
    saved extraction, newest first.
    """
    _ensure_dir()
    rows = []
    for p in sorted(EXTRACTION_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
            rows.append({
                "document_id":         rec.get("document_id"),
                "form_type":           rec.get("form_type"),
                "source_filename":     rec.get("source_filename"),
                "pdf_type":            rec.get("pdf_type"),
                "extracted_at":        rec.get("extracted_at"),
                "last_updated_at":     rec.get("last_updated_at"),
                "document_confidence": rec.get("document_confidence"),
                "exception_count":     len(rec.get("exceptions") or []),
                "escalation_count":    len(rec.get("exception_audit") or []),
            })
        except Exception:
            pass
    return rows
