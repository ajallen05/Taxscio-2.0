"""
backend/adapters/data_integrity_engine.py
==========================================
Adapter for the Data Integrity Engine service (Phase 4 extraction target).

Two call paths, controlled by DATA_INTEGRITY_ENGINE_REMOTE env var:

  LOCAL (default, DATA_INTEGRITY_ENGINE_REMOTE not set or "false")
    Calls services.data_integrity_engine.service functions in-process.
    Zero network overhead.  Used while the monolith is running.

  REMOTE (DATA_INTEGRITY_ENGINE_REMOTE=true)
    Makes an HTTP POST to the Data Integrity Engine microservice at
    DATA_INTEGRITY_ENGINE_URL (default http://localhost:8004).
    Used after the service is deployed behind NGINX.

Switch is a single env var — no code changes needed.

IMPORTANT: this adapter is the ONLY place in the monolith that should call
ValidationEngine, AutoFixer, or Scorer logic.  All /validate, /apply-fixes,
/revalidate, and /extract route validation calls go through here.

LOCAL path note:
  service.validate_document() returns an IntegrityResult Pydantic model.
  service.apply_fixes_document() returns an ApplyFixesResult Pydantic model.
  Both are converted to plain dicts via .model_dump() so main.py receives
  identical shapes in LOCAL and REMOTE modes.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger("Taxscio.adapters.data_integrity_engine")

# ── Environment-driven mode switch ────────────────────────────────────────────
_REMOTE = os.environ.get("DATA_INTEGRITY_ENGINE_REMOTE", "false").lower() == "true"
_REMOTE_URL = os.environ.get("DATA_INTEGRITY_ENGINE_URL", "http://localhost:8004").rstrip("/")
_SERVICE_TOKEN = os.environ.get("DATA_INTEGRITY_ENGINE_TOKEN", "")
_TIMEOUT_SECONDS = float(os.environ.get("DATA_INTEGRITY_ENGINE_TIMEOUT_SECONDS", "60"))


class DataIntegrityEngineAdapter:
    """
    Single entry point for all Data Integrity Engine calls in the monolith.

    Usage (in main.py routes):
        _data_integrity = DataIntegrityEngineAdapter()

        result = _data_integrity.validate(
            form_type=form_type,
            extracted_fields=normalized,
            context=context_dict,
            pdf_type=pdf_type,
        )
        integrity_data = result["data"]
    """

    def validate(
        self,
        form_type: str,
        extracted_fields: dict[str, Any],
        context: dict[str, Any] | None = None,
        pdf_type: str | None = None,
        human_verified_fields: list[str] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Validate extracted fields against IRS rules.

        Returns:
            TaxscioResponse dict:
                ok:         bool (always True — validation is fail-open)
                data:       IntegrityResult dict containing:
                              form_type, confidence, errors, exceptions,
                              fixable_exceptions, review_exceptions,
                              field_confidence, document_confidence,
                              needs_review, review_fields, pdf_type_used,
                              human_verified_fields, summary_validation,
                              request_id
                error:      None (always — validate never returns ok=False)
                request_id: str (internal trace ID)
                service:    "data-integrity-engine"
                version:    "1.0.0"
        """
        payload = self._build_payload(
            form_type=form_type,
            extracted_fields=extracted_fields,
            context=context,
            pdf_type=pdf_type,
            human_verified_fields=human_verified_fields or [],
            request_id=request_id,
        )
        if _REMOTE:
            return self._call_remote(payload, "/api/v1/validate")
        return self._call_local_validate(payload)

    def apply_fixes(
        self,
        form_type: str,
        extracted_fields: dict[str, Any],
        fixes: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
        pdf_type: str | None = None,
        human_verified_fields: list[str] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Apply fix instructions to extracted fields and re-validate.

        Patching happens inside the service (not here) so the REMOTE path
        receives correct unpatched data — the service owns _patch_nested.

        Returns:
            TaxscioResponse dict with data containing everything from validate()
            plus: fixes_applied (int), patched_fields (dict), patch_log (list).
        """
        payload = self._build_payload(
            form_type=form_type,
            extracted_fields=extracted_fields,
            context=context,
            pdf_type=pdf_type,
            human_verified_fields=human_verified_fields or [],
            request_id=request_id,
        )
        payload["fixes"] = fixes
        if _REMOTE:
            return self._call_remote(payload, "/api/v1/apply-fixes")
        return self._call_local_apply_fixes(payload)

    def revalidate(
        self,
        form_type: str,
        extracted_fields: dict[str, Any],
        context: dict[str, Any] | None = None,
        pdf_type: str | None = None,
        human_verified_fields: list[str] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Re-validate after a human edit (semantic alias of validate).

        Returns the same shape as validate().
        """
        payload = self._build_payload(
            form_type=form_type,
            extracted_fields=extracted_fields,
            context=context,
            pdf_type=pdf_type,
            human_verified_fields=human_verified_fields or [],
            request_id=request_id,
        )
        if _REMOTE:
            return self._call_remote(payload, "/api/v1/revalidate")
        return self._call_local_revalidate(payload)

    # ── Payload builder ────────────────────────────────────────────────────────

    @staticmethod
    def _build_payload(
        form_type: str,
        extracted_fields: dict[str, Any],
        context: dict[str, Any] | None,
        pdf_type: str | None,
        human_verified_fields: list[str],
        request_id: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "form_type":            form_type,
            "extracted_fields":     extracted_fields,
            "human_verified_fields": human_verified_fields,
            "context":              context or {},
        }
        if pdf_type is not None:
            payload["pdf_type"] = pdf_type
        if request_id is not None:
            payload["request_id"] = request_id
        return payload

    # ── Local (in-process) paths ───────────────────────────────────────────────

    def _call_local_validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Call internal validation logic directly (monolith path)."""
        from backend.utils.data import flatten_for_validation
        from backend.utils.pipeline import run_validation_pipeline, build_validation_response

        form_type = payload["form_type"]
        nested_data = payload["extracted_fields"]
        pdf_type = payload.get("pdf_type", "digital")
        hv_fields = payload.get("human_verified_fields", [])
        req_id = payload.get("request_id", "")

        # 1. Prepare flat data
        flat_data = flatten_for_validation(nested_data)

        # 2. Run Pipeline
        pipeline_result = run_validation_pipeline(
            form_type=form_type,
            flat_data=flat_data,
            context=payload.get("context", {}),
            pdf_type=pdf_type,
            human_verified_fields=hv_fields,
        )

        # 3. Build standard response (matches microservice schema)
        integrity_result = build_validation_response(
            form_type=form_type,
            pdf_type=pdf_type,
            data=nested_data,
            pipeline_result=pipeline_result,
            human_verified_fields=hv_fields,
            extra={"request_id": req_id}
        )

        return self._wrap_local(integrity_result)

    def _call_local_apply_fixes(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Call internal fix logic directly (monolith path)."""
        nested_data = payload["extracted_fields"]
        fixes = payload.get("fixes", [])

        # 1. Patch the nested data structure
        patched_nested = self._patch_nested(nested_data, fixes)
        payload["extracted_fields"] = patched_nested

        # 2. Run validation on the patched result
        res = self._call_local_validate(payload)

        # 3. Add patching metadata (expected by main.py)
        res["data"]["fixes_applied"] = len(fixes)
        res["data"]["patched_fields"] = patched_nested
        res["data"]["patch_log"] = []

        return res

    def _patch_nested(self, data: dict, fixes: list) -> dict:
        """Apply flat fixes back into a nested structure by searching recursively."""
        import copy
        import re
        result = copy.deepcopy(data) if data is not None else {}
        if not isinstance(result, dict):
            return result

        def _recursive_patch(obj: Any, field_name: str, new_val: Any) -> bool:
            found = False
            if isinstance(obj, dict):
                # Try exact key match
                if field_name in obj:
                    obj[field_name] = new_val
                    found = True
                
                # Check for box_N_ prefix strip match (matches flatten_for_validation logic)
                for k in list(obj.keys()):
                    bare_k = re.sub(r'^box_[\da-zA-Z]+_', '', k)
                    bare_k = re.sub(r'^box_[\da-zA-Z]+$', '', bare_k) or k
                    if bare_k == field_name:
                        obj[k] = new_val
                        found = True
                    
                    # Also recurse to catch nested instances or sub-dicts
                    if _recursive_patch(obj[k], field_name, new_val):
                        found = True
            elif isinstance(obj, list):
                for item in obj:
                    if _recursive_patch(item, field_name, new_val):
                        found = True
            return found

        for fix in fixes:
            field = fix.get("field")
            val = fix.get("new_value")
            if not field: continue
            _recursive_patch(result, field, val)
        return result

    def _call_local_revalidate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Call internal validation logic (alias of validate in monolith)."""
        return self._call_local_validate(payload)

    @staticmethod
    def _wrap_local(data_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Wrap a service result dict in the TaxscioResponse envelope shape,
        so main.py receives identical shapes in LOCAL and REMOTE modes.
        """
        return {
            "ok":         True,
            "service":    "data-integrity-engine",
            "version":    "1.0.0",
            "request_id": f"local_{data_dict.get('request_id', '')}",
            "error":      None,
            "data":       data_dict,
        }

    # ── Remote (HTTP) path ────────────────────────────────────────────────────

    def _call_remote(self, payload: dict[str, Any], path: str) -> dict[str, Any]:
        """POST to the Data Integrity Engine microservice over HTTP."""
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "httpx is required for remote Data Integrity Engine calls. "
                "Add httpx to requirements.txt."
            ) from exc

        url = f"{_REMOTE_URL}{path}"
        headers = {"Content-Type": "application/json"}
        if _SERVICE_TOKEN:
            headers["Authorization"] = f"Bearer {_SERVICE_TOKEN}"

        log.debug(
            "DataIntegrityEngineAdapter remote POST %s form=%s",
            url, payload.get("form_type"),
        )

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
                f"Data Integrity Engine timed out after {_TIMEOUT_SECONDS}s: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Data Integrity Engine returned HTTP {exc.response.status_code}: "
                f"{exc.response.text[:200]}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Data Integrity Engine unreachable at {url}: {exc}"
            ) from exc

        return response.json()
