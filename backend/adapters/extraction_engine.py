"""
backend/adapters/extraction_engine.py
========================================
Adapter for the Extraction Engine service (Phase 3 extraction target).

Two call paths, controlled by EXTRACTION_ENGINE_REMOTE env var:

  LOCAL (default, EXTRACTION_ENGINE_REMOTE not set or "false")
    Calls services.extraction_engine.service.extract_document() in-process.
    Zero network overhead.  Used while the monolith is running.

  REMOTE (EXTRACTION_ENGINE_REMOTE=true)
    Makes an HTTP POST to the Extraction Engine microservice at
    EXTRACTION_ENGINE_URL (default http://localhost:8003).
    Used after the service is deployed behind NGINX.

Switch is a single env var — no code changes needed.

IMPORTANT: this adapter is the ONLY place in the monolith that should call
OCR or NuExtract logic for the purpose of field extraction.  All /extract
route calls go through extract_for_pipeline() here.

Note on document_bytes encoding:
  LOCAL path: base64-encodes raw bytes before passing to ExtractRequest,
    because ExtractRequest.document_bytes is typed str | None and
    service.py's _decode_bytes() expects a base64 string.
  REMOTE path: same base64 encoding for JSON transport.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

log = logging.getLogger("Taxscio.adapters.extraction_engine")

# ── Environment-driven mode switch ────────────────────────────────────────────
_REMOTE = os.environ.get("EXTRACTION_ENGINE_REMOTE", "false").lower() == "true"
_REMOTE_URL = os.environ.get("EXTRACTION_ENGINE_URL", "http://localhost:8003").rstrip("/")
_SERVICE_TOKEN = os.environ.get("EXTRACTION_ENGINE_TOKEN", "")
_TIMEOUT_SECONDS = float(os.environ.get("EXTRACTION_ENGINE_TIMEOUT_SECONDS", "120"))


class ExtractionFailedError(Exception):
    """
    Raised by extract_for_pipeline() when the Extraction Engine returns ok=false.

    Attributes:
        code:    Short error code string (e.g. "SCHEMA_NOT_FOUND").
        message: Human-readable error description.
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class ExtractionEngineAdapter:
    """
    Single entry point for all Extraction Engine calls in the monolith.

    Usage (in main.py routes):
        _extraction_engine = ExtractionEngineAdapter()

        input_text, normalized, ocr_source, extraction_latency = \\
            _extraction_engine.extract_for_pipeline(
                document_bytes=file_bytes,
                form_type=form_type,
                pdf_type=pdf_type,
            )
    """

    def extract(
        self,
        document_bytes: bytes,
        form_type: str,
        pdf_type: str | None = None,
        schema_override: dict | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Extract structured fields from a document.

        Args:
            document_bytes:  Raw PDF bytes.
            form_type:       IRS form type string (e.g. "W-2").
            pdf_type:        "digital" | "scanned" | None (auto-detect).
                             When supplied by the Document Validator, accepted as-is.
            schema_override: Optional NuExtract schema override for this call only.
            request_id:      Client idempotency key (echoed in data.request_id).

        Returns:
            Full TaxscioResponse dict:
                ok:         bool
                data:       ExtractResult dict (extracted_fields, raw_text, ocr_source, ...)
                error:      str | None
                request_id: str  (internal trace ID, starts with "trace_")
                service:    "extraction-engine"
                version:    "1.0.0"
        """
        # Both paths need base64-encoded bytes — service.py's _decode_bytes
        # expects a base64 string, and JSON transport requires it for REMOTE.
        b64_bytes = base64.b64encode(document_bytes).decode("utf-8")

        kwargs: dict[str, Any] = {
            "document_bytes": b64_bytes,
            "form_type":      form_type,
        }
        if pdf_type is not None:
            kwargs["pdf_type"] = pdf_type
        if schema_override is not None:
            kwargs["schema_override"] = schema_override
        if request_id is not None:
            kwargs["request_id"] = request_id

        if _REMOTE:
            return self._call_remote(kwargs)
        return self._call_local(kwargs)

    def extract_for_pipeline(
        self,
        document_bytes: bytes,
        form_type: str,
        pdf_type: str | None = None,
        schema_override: dict | None = None,
        request_id: str | None = None,
    ) -> tuple[str, dict[str, Any], str, float]:
        """
        Convenience method for main.py pipeline.

        Returns:
            (input_text, normalized, ocr_source, extraction_latency_seconds)

            input_text:               Raw text sent to NuExtract (may be "" on
                                      qwen_fallback path or fail-open).
            normalized:               extracted_fields dict from the Extraction Engine.
            ocr_source:               "pymupdf4llm" | "paddleocr" | "qwen_fallback" |
                                      "unknown" (on fail-open).
            extraction_latency_seconds: Full pipeline latency in seconds (float).

        Raises:
            ExtractionFailedError: When ok=false (malformed request path).
                                   Note: fail-open results have ok=true with
                                   empty extracted_fields — those do NOT raise.
        """
        result = self.extract(
            document_bytes=document_bytes,
            form_type=form_type,
            pdf_type=pdf_type,
            schema_override=schema_override,
            request_id=request_id,
        )

        if not result.get("ok", True):
            # ok=false is reserved for malformed requests — surface as error
            error_msg = result.get("error") or "Extraction Engine returned ok=false"
            raise ExtractionFailedError("EXTRACTION_FAILED", error_msg)

        data = result.get("data") or {}
        input_text = data.get("raw_text") or ""
        normalized = data.get("extracted_fields") or {}
        ocr_source = data.get("ocr_source") or "unknown"
        metadata = data.get("extraction_metadata") or {}
        latency_ms = metadata.get("latency_ms") or 0
        extraction_latency = round(latency_ms / 1000, 3)

        log.debug(
            "extract_for_pipeline form=%s ocr=%s fields=%d latency=%.3fs",
            form_type, ocr_source, len(normalized), extraction_latency,
        )

        return input_text, normalized, ocr_source, extraction_latency

    def extract_from_text(
        self,
        raw_text: str,
        form_type: str,
        ocr_source: str | None = None,
        request_id: str | None = None,
    ) -> tuple[str, dict[str, Any], str, float]:
        """
        Extract fields from pre-extracted text (no OCR needed).

        Uses the text-based extraction path added in Step 2. Skips OCR
        entirely — goes straight to NuExtract normalization.

        Returns the same tuple as extract_for_pipeline():
            (input_text, normalized, ocr_source, extraction_latency_seconds)
        """
        if _REMOTE:
            result = self._call_remote_text(raw_text, form_type, ocr_source, request_id)
        else:
            result = self._call_local_text(raw_text, form_type, ocr_source, request_id)

        if not result.get("ok", True):
            error_msg = result.get("error") or "Extraction Engine returned ok=false"
            raise ExtractionFailedError("EXTRACTION_FAILED", error_msg)

        data = result.get("data") or {}
        input_text = data.get("raw_text") or raw_text
        normalized = data.get("extracted_fields") or {}
        source = data.get("ocr_source") or ocr_source or "text_input"
        metadata = data.get("extraction_metadata") or {}
        latency_ms = metadata.get("latency_ms") or 0
        extraction_latency = round(latency_ms / 1000, 3)

        log.debug(
            "extract_from_text form=%s ocr=%s fields=%d latency=%.3fs",
            form_type, source, len(normalized), extraction_latency,
        )

        return input_text, normalized, source, extraction_latency

    def _call_local_text(
        self,
        raw_text: str,
        form_type: str,
        ocr_source: str | None,
        request_id: str | None,
    ) -> dict[str, Any]:
        """Call internal normalization logic directly (monolith path)."""
        import time
        from backend.utils.schemas import get_schema
        from backend.extraction.nuextract_normalizer import normalize

        t0 = time.time()
        schema = get_schema(form_type)
        if not schema:
            return {"ok": False, "error": f"Schema not found for form {form_type}"}

        normalized = normalize(schema=schema, input_text=raw_text)
        latency_ms = int((time.time() - t0) * 1000)

        return {
            "ok": True,
            "service": "extraction-engine",
            "version": "1.0.0",
            "request_id": f"local_{request_id or 'unknown'}",
            "error": None,
            "data": {
                "extracted_fields": normalized,
                "raw_text": raw_text,
                "ocr_source": ocr_source or "text_input",
                "extraction_metadata": {
                    "latency_ms": latency_ms,
                    "model": "NuExtract 2.0 PRO"
                }
            },
        }

    def _call_remote_text(
        self,
        raw_text: str,
        form_type: str,
        ocr_source: str | None,
        request_id: str | None,
    ) -> dict[str, Any]:
        """POST to /api/v1/extract-text on the Extraction Engine microservice."""
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "httpx is required for remote Extraction Engine calls."
            ) from exc

        url = f"{_REMOTE_URL}/api/v1/extract-text"
        headers = {"Content-Type": "application/json"}
        if _SERVICE_TOKEN:
            headers["Authorization"] = f"Bearer {_SERVICE_TOKEN}"

        payload = {
            "raw_text": raw_text,
            "form_type": form_type,
        }
        if ocr_source is not None:
            payload["ocr_source"] = ocr_source
        if request_id is not None:
            payload["request_id"] = request_id

        log.debug("ExtractionEngineAdapter remote POST %s form=%s", url, form_type)

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
                f"Extraction Engine text timed out after {_TIMEOUT_SECONDS}s: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Extraction Engine text returned HTTP {exc.response.status_code}: "
                f"{exc.response.text[:200]}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Extraction Engine text unreachable at {url}: {exc}"
            ) from exc

        return response.json()

    # ── Local (in-process) path ───────────────────────────────────────────────

    def _call_local(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Call internal extraction logic directly (monolith path)."""
        import time
        from backend.utils.schemas import get_schema
        from backend.ingestion.pdf_router import route_pdf_with_preprocessing, route_image
        from backend.ingestion.ocr_engine import run_ocr
        from backend.extraction.nuextract_normalizer import normalize

        t0 = time.time()
        form_type = payload.get("form_type", "")
        b64_str = payload.get("document_bytes", "")
        file_bytes = base64.b64decode(b64_str) if b64_str else b""
        req_id = payload.get("request_id", "local")

        # 1. Get Schema
        schema = payload.get("schema_override") or get_schema(form_type)
        if not schema:
            return {"ok": False, "error": f"Schema not found for form {form_type}"}

        # 2. Route & Extract Text
        if file_bytes.startswith(b"%PDF"):
            pdf_type, content = route_pdf_with_preprocessing(file_bytes)
        else:
            pdf_type, content = route_image(file_bytes)

        if isinstance(content, str):
            raw_text = content
            ocr_source = "pymupdf4llm"
            normalized = normalize(schema=schema, input_text=raw_text)
        else:
            # Scanned path: content is list of images
            try:
                ocr_res = run_ocr(content, form_type=form_type, raise_on_low_confidence=False)
                raw_text = ocr_res["text"]
                ocr_source = "paddleocr"
                normalized = normalize(schema=schema, input_text=raw_text)
            except (ImportError, Exception) as exc:
                # Fallback to NuExtract Vision path if local OCR is unavailable or fails
                log.warning("[extraction_engine] OCR unavailable (%s), falling back to NuExtract Vision", exc)
                normalized = normalize(schema=schema, input_file=file_bytes)
                raw_text = "[Extracted via NuExtract Vision fallback]"
                ocr_source = "nuextract_vision"

        latency_ms = int((time.time() - t0) * 1000)

        return {
            "ok": True,
            "service": "extraction-engine",
            "version": "1.0.0",
            "request_id": f"local_{req_id}",
            "error": None,
            "data": {
                "extracted_fields": normalized,
                "raw_text": raw_text,
                "ocr_source": ocr_source,
                "extraction_metadata": {
                    "latency_ms": latency_ms,
                    "model": "NuExtract 2.0 PRO"
                }
            }
        }

    # ── Remote (HTTP) path ────────────────────────────────────────────────────

    def _call_remote(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST to the Extraction Engine microservice over HTTP."""
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "httpx is required for remote Extraction Engine calls. "
                "Add httpx to requirements.txt."
            ) from exc

        url = f"{_REMOTE_URL}/api/v1/extract"
        headers = {"Content-Type": "application/json"}
        if _SERVICE_TOKEN:
            headers["Authorization"] = f"Bearer {_SERVICE_TOKEN}"

        log.debug("ExtractionEngineAdapter remote POST %s form=%s", url, payload.get("form_type"))

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
                f"Extraction Engine timed out after {_TIMEOUT_SECONDS}s: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Extraction Engine returned HTTP {exc.response.status_code}: "
                f"{exc.response.text[:200]}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Extraction Engine unreachable at {url}: {exc}"
            ) from exc

        return response.json()
