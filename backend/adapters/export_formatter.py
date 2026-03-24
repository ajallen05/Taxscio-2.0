"""
backend/adapters/export_formatter.py
======================================
Adapter for the Export Formatter service (Phase 1 extraction target).

Provides two call paths controlled by the EXPORT_FORMATTER_REMOTE env var:

  LOCAL (default, EXPORT_FORMATTER_REMOTE not set or "false")
    Calls the service logic in-process: imports and calls
    services.export_formatter.service.format_document() directly.
    Zero network overhead.  Used while the monolith is running.

  REMOTE (EXPORT_FORMATTER_REMOTE=true)
    Makes an HTTP POST to the Export Formatter microservice at
    EXPORT_FORMATTER_URL (default http://localhost:8001).
    Used after the service is deployed behind NGINX.

The caller never knows which path is active.  Switching from LOCAL to REMOTE
is a one-env-var change with no code modifications.

IMPORTANT: this adapter is the ONLY place in the monolith that should know
about the Export Formatter.  All routes call format_extraction() here.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger("Taxscio.adapters.export_formatter")

# ── Environment-driven mode switch ────────────────────────────────────────────
_REMOTE = os.environ.get("EXPORT_FORMATTER_REMOTE", "false").lower() == "true"
_REMOTE_URL = os.environ.get("EXPORT_FORMATTER_URL", "http://localhost:8002").rstrip("/")
_SERVICE_TOKEN = os.environ.get("EXPORT_FORMATTER_SERVICE_TOKEN", "")
_TIMEOUT_SECONDS = float(os.environ.get("EXPORT_FORMATTER_TIMEOUT", "10"))


class ExportFormatterAdapter:
    """
    Single entry point for all Export Formatter calls in the monolith.

    Usage (in main.py routes):
        _export = ExportFormatterAdapter()

        result = _export.format_extraction(
            form_type="W-2",
            validated_data=normalized,
            pipeline_result=pipeline,
            pdf_type=pdf_type,
            ocr_source=ocr_source,
            latency=latency,
            raw_extracted_text=input_text,
            correction_log=[],
            human_verified_fields=[],
            client_metadata={},
        )
        # result is the complete response dict (same shape as build_validation_response output
        # plus the Export Formatter fields: record_id, formatted_json, csv_row, summary)
    """

    def format_extraction(
        self,
        form_type: str,
        validated_data: dict[str, Any],
        pipeline_result: dict[str, Any],
        pdf_type: str,
        ocr_source: str = "",
        latency: dict[str, Any] | None = None,
        raw_extracted_text: str = "",
        correction_log: list | None = None,
        human_verified_fields: list | None = None,
        client_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Format a validated extraction result.

        Merges the pipeline_result (from run_validation_pipeline) with the
        Export Formatter's structured outputs (record_id, formatted_json,
        csv_row, summary).

        Args:
            form_type:             IRS form type string.
            validated_data:        Nested extraction result (normalized dict).
            pipeline_result:       Output of run_validation_pipeline().
            pdf_type:              "digital" or "scanned".
            ocr_source:            OCR engine that produced the text.
            latency:               Timing breakdown dict.
            raw_extracted_text:    Raw OCR/markdown text before NuExtract.
            correction_log:        Correction log (empty for human edits).
            human_verified_fields: Fields confirmed by a human.
            client_metadata:       Arbitrary metadata to pass through.

        Returns:
            Merged response dict containing both the standard validation
            response fields AND the export formatter fields.
        """
        if correction_log is None:
            correction_log = []
        if human_verified_fields is None:
            human_verified_fields = []
        if latency is None:
            latency = {}
        if client_metadata is None:
            client_metadata = {}

        val_result = pipeline_result["val_result"]
        fixable    = pipeline_result["fixable_exceptions"]
        review     = pipeline_result["review_exceptions"]
        conf       = pipeline_result["confidence_result"]

        # Build the FormatRequest payload (shared by both paths)
        format_payload = {
            "form_type":            form_type,
            "validated_data":       validated_data,
            "exceptions_resolved":  _exceptions_to_resolved(val_result["exceptions"]),
            "document_confidence":  conf["document_confidence"],
            "needs_review":         conf["needs_review"],
            "field_confidence":     conf["field_scores"],
            "client_metadata":      client_metadata,
        }

        if _REMOTE:
            export_result = self._call_remote(format_payload)
        else:
            export_result = self._call_local(format_payload)

        # Merge: standard validation fields + export formatter outputs + extras
        return {
            # Validation fields
            "form_type":             form_type,
            "pdf_type":              pdf_type,
            "confidence":            val_result["confidence"],
            "errors":                val_result["errors"],
            "exceptions":            val_result["exceptions"],
            "summary_validation":    val_result.get("summary", {}),
            "fixable_exceptions":    fixable,
            "review_exceptions":     review,
            "data":                  validated_data,
            "field_confidence":      conf["field_scores"],
            "document_confidence":   conf["document_confidence"],
            "needs_review":          conf["needs_review"],
            "review_fields":         conf["review_fields"],
            "human_verified_fields": human_verified_fields,
            # Extra pipeline context
            "ocr_source":            ocr_source,
            "latency":               latency,
            "raw_extracted_text":    raw_extracted_text,
            "raw_normalized_json":   validated_data,
            "correction_log":        correction_log,
            # Export Formatter outputs
            "record_id":             export_result.get("record_id", ""),
            "formatted_json":        export_result.get("formatted_json", {}),
            "csv_row":               export_result.get("csv_row", {}),
            "summary":               export_result.get("summary", {}),
        }

    # ── Local (in-process) path ───────────────────────────────────────────────

    def _call_local(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Formulate a basic export response (monolith fallback)."""
        import uuid
        from backend.utils.data import flatten_for_validation
        
        form_type = payload.get("form_type", "Unknown")
        nested_data = payload.get("validated_data", {})
        
        # 1. Create a record ID
        record_id = str(uuid.uuid4())
        
        # 2. Simple CSV row (flattened data)
        flat_data = flatten_for_validation(nested_data)
        
        # 3. Summary
        summary = {
            "form_type": form_type,
            "fields_count": len(flat_data),
            "status": "ready"
        }
        
        return {
            "record_id":      record_id,
            "formatted_json": nested_data,
            "csv_row":        flat_data,
            "summary":        summary,
        }

    # ── Remote (HTTP) path ────────────────────────────────────────────────────

    def _call_remote(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST to the Export Formatter microservice over HTTP."""
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "httpx is required for remote Export Formatter calls. "
                "Add httpx to requirements.txt."
            ) from exc

        url = f"{_REMOTE_URL}/api/v1/format"
        headers = {"Content-Type": "application/json"}
        if _SERVICE_TOKEN:
            headers["Authorization"] = f"Bearer {_SERVICE_TOKEN}"

        log.debug("ExportFormatterAdapter remote POST %s", url)

        try:
            response = httpx.post(
                url,
                content=json.dumps(payload, default=str),
                headers=headers,
                timeout=_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"Export Formatter timed out after {_TIMEOUT_SECONDS}s: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Export Formatter returned HTTP {exc.response.status_code}: "
                f"{exc.response.text[:200]}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Export Formatter unreachable at {url}: {exc}"
            ) from exc

        body = response.json()
        if not body.get("ok"):
            raise RuntimeError(
                f"Export Formatter error: {body.get('error', 'unknown')}"
            )

        return body.get("data", {})


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _exceptions_to_resolved(exceptions: list[dict]) -> list[dict]:
    """
    Convert ValidationEngine exception dicts to the ResolvedExceptionItem
    shape expected by the Export Formatter.

    ValidationEngine exceptions have keys: field, rule, message, severity, value.
    We map these to: field, rule, original_value, resolution.
    Exceptions at this stage are unresolved (they haven't been fixed yet) —
    we label them as 'unresolved' so the formatter can count them correctly.
    """
    resolved = []
    for exc in exceptions:
        resolved.append({
            "field":          exc.get("field", ""),
            "rule":           exc.get("rule", exc.get("code", "")),
            "original_value": exc.get("value"),
            "resolution":     "unresolved",
        })
    return resolved
