"""
backend/adapters/document_validator.py
========================================
Adapter for the Document Validator service (Phase 2 extraction target).

Two call paths, controlled by DOCUMENT_VALIDATOR_REMOTE env var:

  LOCAL (default, DOCUMENT_VALIDATOR_REMOTE not set or "false")
    Calls services.document_validator.service.validate_document() in-process.
    Zero network overhead.  Used while the monolith is running.

  REMOTE (DOCUMENT_VALIDATOR_REMOTE=true)
    Makes an HTTP POST to the Document Validator microservice at
    DOCUMENT_VALIDATOR_URL (default http://localhost:8001).
    Used after the service is deployed behind NGINX.

Switch is a single env var — no code changes needed.

IMPORTANT: this adapter is the ONLY place in the monolith that should call
gate or routing logic for the purpose of document validation.  All routes
call validate_pdf() or validate_text() here.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

log = logging.getLogger("Taxscio.adapters.document_validator")

# ── Environment-driven mode switch ────────────────────────────────────────────
_REMOTE = os.environ.get("DOCUMENT_VALIDATOR_REMOTE", "false").lower() == "true"
_REMOTE_URL = os.environ.get("DOCUMENT_VALIDATOR_URL", "http://localhost:8001").rstrip("/")
_SERVICE_TOKEN = os.environ.get("DOCUMENT_VALIDATOR_SERVICE_TOKEN", "")
_TIMEOUT_SECONDS = float(os.environ.get("DOCUMENT_VALIDATOR_TIMEOUT", "15"))


class DocumentValidatorAdapter:
    """
    Single entry point for all Document Validator calls in the monolith.

    Usage (in main.py routes):
        _doc_validator = DocumentValidatorAdapter()

        # Validate a raw PDF bytes object:
        result = _doc_validator.validate_pdf(file_bytes)
        if not result["is_valid_tax_form"] and result["confidence_score"] != -1:
            return jsonify({"error": "Not an IRS tax form"}), 422

        pdf_type = result["pdf_type"]            # "digital" or "scanned"
        form_type = result["form_type"]          # detected form type or None

    Fail-open contract:
        If confidence_score == -1, the gate failed technically.
        The pipeline must continue (fail-open) rather than reject the document.
    """

    def validate_pdf(
        self,
        file_bytes: bytes,
        source: str = "upload",
        client_id: str = "",
        request_id: str = "",
    ) -> dict[str, Any]:
        """
        Validate a PDF document.

        Args:
            file_bytes:  Raw PDF bytes.
            source:      Document source label (for logging).
            client_id:   Ledger client identifier.
            request_id:  Client idempotency key.

        Returns:
            ValidateResult as a plain dict:
                is_valid_tax_form: bool
                form_type:         str | None
                pdf_type:          "digital" | "scanned" | None
                confidence_score:  int (-1 = fail-open, 0-100 = gate score)
                omb_number:        str | None
                tax_year:          int | None
                signals_found:     list[str]
                rejection_reason:  str | None
                page_count:        int
                preprocessing_applied: bool
                request_id:        str
                _gate_error:       str | None (only on fail-open)
        """
        b64 = base64.b64encode(file_bytes).decode()
        payload = {
            "document_bytes": b64,
            "source": source,
            "client_id": client_id or "",
            "request_id": request_id or "",
        }
        return self._dispatch(payload)

    def validate_text(
        self,
        text: str,
        source: str = "ocr",
        client_id: str = "",
        request_id: str = "",
    ) -> dict[str, Any]:
        """
        Validate a document that has already been converted to text (OCR output).

        Because the Document Validator service expects bytes, this path
        encodes the text as UTF-8 and passes it as document_bytes with
        a text/plain indicator in source.  The gate heuristic works on text
        extracted from the bytes, so this is equivalent.

        For the LOCAL path, calls gate.verify_text() directly (more efficient).
        For the REMOTE path, encodes as bytes (identical gate result).
        """
        if not _REMOTE:
            return self._call_local_text(text, source, client_id, request_id)

        # Remote path: encode text as pseudo-PDF bytes (gate reads embedded text)
        text_bytes = text.encode("utf-8")
        b64 = base64.b64encode(text_bytes).decode()
        payload = {
            "document_bytes": b64,
            "source": source,
            "client_id": client_id or "",
            "request_id": request_id or "",
        }
        return self._dispatch(payload)

    def validate_upload(
        self,
        file_bytes: bytes,
        filename: str = "upload.pdf",
        source: str = "file_upload",
        request_id: str = "",
    ) -> dict[str, Any]:
        """
        Validate a document via multipart file upload.

        Uses /api/v1/validate-upload on REMOTE, or falls back to the
        standard validate_pdf() path on LOCAL (which already handles bytes).

        Returns the same ValidateResult dict as validate_pdf(), but the
        REMOTE path includes raw_text from the Document Validator's
        text extraction pipeline.
        """
        if not _REMOTE:
            # LOCAL path: validate_pdf already handles bytes
            return self.validate_pdf(
                file_bytes=file_bytes,
                source=source,
                request_id=request_id,
            )

        # REMOTE path: multipart upload to /api/v1/validate-upload
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "httpx is required for remote Document Validator calls."
            ) from exc

        url = f"{_REMOTE_URL}/api/v1/validate-upload"
        headers = {}
        if _SERVICE_TOKEN:
            headers["Authorization"] = f"Bearer {_SERVICE_TOKEN}"

        log.debug("DocumentValidatorAdapter remote multipart POST %s", url)

        try:
            response = httpx.post(
                url,
                files={"file": (filename, file_bytes, "application/pdf")},
                headers=headers,
                timeout=_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            log.warning("Document Validator upload timed out: %s — fail open", exc)
            return _fail_open_dict(request_id)
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            log.warning("Document Validator upload unreachable: %s — fail open", exc)
            return _fail_open_dict(request_id)

        body = response.json()
        if not body.get("ok"):
            log.warning("Document Validator upload returned ok=false: %s — fail open", body.get("error"))
            return _fail_open_dict(request_id)

        return body.get("data", _fail_open_dict(request_id))

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def _dispatch(self, payload: dict[str, Any]) -> dict[str, Any]:
        if _REMOTE:
            return self._call_remote(payload)
        return self._call_local(payload)

    # ── Local (in-process) path ───────────────────────────────────────────────

    def _call_local(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Call internal gate logic directly (monolith path)."""
        from backend.adapters.gate import GateAdapter
        gate = GateAdapter()

        b64_str = payload.get("document_bytes", "")
        file_bytes = base64.b64decode(b64_str) if b64_str else b""
        request_id = payload.get("request_id", "")

        # Call the monolith gate logic
        gate_result = gate.verify_pdf(file_bytes)

        # Map to the unified adapter response format
        is_valid = gate_result.get("is_tax_form", True)
        score = gate_result.get("score", -1)

        # Digital vs Scanned heuristic (score -1 means insufficient text found by pymupdf)
        pdf_type = "scanned" if score == -1 else "digital"

        return {
            "is_valid_tax_form":    is_valid,
            "form_type":            gate_result.get("form_type"),
            "pdf_type":             pdf_type,
            "confidence_score":     score,
            "omb_number":           gate_result.get("omb_number"),
            "tax_year":             gate_result.get("tax_year"),
            "signals_found":        gate_result.get("signals_found", []),
            "rejection_reason":     gate_result.get("rejection_reason"),
            "page_count":           0,
            "preprocessing_applied": False,
            "request_id":           request_id,
            "_gate_error":          gate_result.get("error"),
        }

    def _call_local_text(
        self,
        text: str,
        source: str,
        client_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        """
        Direct gate.verify_text() call for the LOCAL text validation path.

        More efficient than encoding text as bytes and routing through the
        full pipeline just to get to verify_text().
        """
        try:
            from backend.adapters.gate import GateAdapter
            gate = GateAdapter()
            gate_result = gate.verify_text(text)

            is_valid = gate_result.get("is_tax_form", True)
            score = gate_result.get("score", -1)
            gate_error = gate_result.get("error")

            if gate_error and score == -1:
                return _fail_open_dict(request_id or "")

            rejection_reason = gate_result.get("rejection_reason")
            if not is_valid and not rejection_reason:
                rejection_reason = f"No IRS signals detected (score={score}, threshold=30)"

            return {
                "is_valid_tax_form":    is_valid,
                "form_type":            gate_result.get("form_type"),
                "pdf_type":             None,       # not determined from text alone
                "confidence_score":     score,
                "omb_number":           gate_result.get("omb_number"),
                "tax_year":             gate_result.get("tax_year"),
                "signals_found":        gate_result.get("signals_found", []),
                "rejection_reason":     rejection_reason,
                "page_count":           0,
                "preprocessing_applied": False,
                "request_id":           request_id or "",
                "_gate_error":          None,
            }
        except Exception as exc:
            log.warning("DocumentValidatorAdapter.validate_text local gate failed: %s", exc)
            return _fail_open_dict(request_id or "")

    # ── Remote (HTTP) path ────────────────────────────────────────────────────

    def _call_remote(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST to the Document Validator microservice over HTTP."""
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "httpx is required for remote Document Validator calls. "
                "Add httpx to requirements.txt."
            ) from exc

        url = f"{_REMOTE_URL}/api/v1/validate"
        headers = {"Content-Type": "application/json"}
        if _SERVICE_TOKEN:
            headers["Authorization"] = f"Bearer {_SERVICE_TOKEN}"

        log.debug("DocumentValidatorAdapter remote POST %s", url)

        try:
            response = httpx.post(
                url,
                content=json.dumps(payload, default=str),
                headers=headers,
                timeout=_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            log.warning("Document Validator timed out: %s — fail open", exc)
            return _fail_open_dict(payload.get("request_id", ""))
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            log.warning("Document Validator unreachable: %s — fail open", exc)
            return _fail_open_dict(payload.get("request_id", ""))

        body = response.json()
        if not body.get("ok"):
            log.warning("Document Validator returned ok=false: %s — fail open", body.get("error"))
            return _fail_open_dict(payload.get("request_id", ""))

        return body.get("data", _fail_open_dict(payload.get("request_id", "")))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _result_to_dict(result) -> dict[str, Any]:
    """Convert a ValidateResult Pydantic model to a plain dict."""
    d = result.model_dump(by_alias=True)
    return d


def _fail_open_dict(request_id: str) -> dict[str, Any]:
    """Return the canonical fail-open dict (no Pydantic model needed here)."""
    return {
        "is_valid_tax_form":     True,
        "form_type":             None,
        "pdf_type":              None,
        "confidence_score":      -1,
        "omb_number":            None,
        "tax_year":              None,
        "signals_found":         [],
        "rejection_reason":      None,
        "page_count":            0,
        "preprocessing_applied": False,
        "request_id":            request_id,
        "_gate_error":           "adapter fail-open",
    }
