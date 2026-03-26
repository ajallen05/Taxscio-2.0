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
_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
_GEMINI_TIMEOUT_SECONDS = float(os.environ.get("GEMINI_TIMEOUT", "15"))


def _candidate_gemini_models(configured_model: str) -> list[str]:
    """Return model IDs to try, preserving user choice first."""
    if configured_model == "gemini-1.5-flash":
        return [
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash-002",
        ]
    return [configured_model]


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
        
        # 3. Summary (AI-first with deterministic fallback)
        summary = self._build_summary(
            form_type=form_type,
            flat_data=flat_data,
            nested_data=nested_data,
            exceptions_resolved=payload.get("exceptions_resolved", []),
            document_confidence=payload.get("document_confidence"),
            needs_review=payload.get("needs_review"),
        )
        
        return {
            "record_id":      record_id,
            "formatted_json": nested_data,
            "csv_row":        flat_data,
            "summary":        summary,
        }

    def _build_summary(
        self,
        form_type: str,
        flat_data: dict[str, Any],
        nested_data: dict[str, Any],
        exceptions_resolved: list[dict[str, Any]],
        document_confidence: float | None,
        needs_review: bool | None,
    ) -> dict[str, Any]:
        """Generate an AI summary using Gemini; fallback to unavailable status only."""
        fallback = {
            "form_type": form_type,
            "fields_count": len(flat_data),
            "status": "unavailable",
            "summary_text": "AI summary is currently unavailable. Please retry.",
            "generated_by": "ai-unavailable",
        }

        if not _GEMINI_API_KEY:
            return fallback

        prompt_payload = {
            "form_type": form_type,
            "fields_count": len(flat_data),
            "sample_fields": dict(list(flat_data.items())[:20]),
            "exceptions_count": len(exceptions_resolved),
            "exceptions": exceptions_resolved[:10],
            "document_confidence": document_confidence,
            "needs_review": bool(needs_review),
            "raw_data": nested_data,
        }

        prompt = (
            "You are a tax document summarization assistant. "
            "Write a concise operational summary for internal CPA workflow. "
            "Return only plain text (no markdown) in 3-5 short sentences. "
            "Include: document type, extracted data quality, major exception patterns, "
            "and recommended next action.\n\n"
            f"Input JSON:\n{json.dumps(prompt_payload, default=str)}"
        )

        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 220,
            },
        }

        try:
            import httpx

            last_exc: Exception | None = None
            for model_name in _candidate_gemini_models(_GEMINI_MODEL):
                url = (
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model_name}:generateContent"
                )
                try:
                    response = httpx.post(
                        url,
                        content=json.dumps(body),
                        headers={
                            "Content-Type": "application/json",
                            "x-goog-api-key": _GEMINI_API_KEY,
                        },
                        timeout=_GEMINI_TIMEOUT_SECONDS,
                    )
                    response.raise_for_status()
                    data = response.json()
                    ai_text = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                        .strip()
                    )
                    if not ai_text:
                        continue

                    return {
                        "form_type": form_type,
                        "fields_count": len(flat_data),
                        "status": "ready",
                        "summary_text": ai_text,
                        "generated_by": "gemini",
                        "model": model_name,
                    }
                except httpx.HTTPStatusError as exc:
                    last_exc = exc
                    if exc.response is not None and exc.response.status_code == 404:
                        # Try next known alias for this model family.
                        continue
                    break
                except Exception as exc:
                    last_exc = exc
                    break

            if last_exc is not None:
                raise last_exc
            return fallback
        except Exception as exc:
            log.warning("Gemini summary fallback activated: %s", exc)
            return fallback

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
