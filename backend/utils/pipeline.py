"""
backend/utils/pipeline.py
=========================
Reusable validation pipeline helper.

The validate → classify → score pattern was copy-pasted identically into
three separate routes (/validate, /apply-fixes, /revalidate).  This module
extracts it into a single testable function (Issue 23 / Issue 24 — DRY fix).

Functions
---------
run_validation_pipeline(...)   — run validation, classification, and scoring
build_validation_response(...) — build the standard route response dict
"""

import logging
from typing import Any

log = logging.getLogger("Taxscio.utils.pipeline")


def run_validation_pipeline(
    form_type: str,
    flat_data: dict,
    context: dict,
    pdf_type: str,
    human_verified_fields: list,
    correction_log: list | None = None,
) -> dict:
    """
    Run the three-stage post-extraction pipeline:
      1. ValidationEngine.validate()
      2. classify_exceptions()
      3. score_extraction()

    Args:
        form_type:             IRS form type string.
        flat_data:             Flat dict from flatten_for_validation().
        context:               Context dict from request (may be {}).
        pdf_type:              "digital" or "scanned".
        human_verified_fields: List of field names confirmed by a human.
        correction_log:        Correction log from a prior correction pass.
                               Defaults to [] (no automated corrections).

    Returns:
        {
            "val_result":          dict from ValidationEngine,
            "fixable_exceptions":  list,
            "review_exceptions":   list,
            "confidence_result":   dict from score_extraction,
        }
    """
    from backend.validation.engine import ValidationEngine
    from backend.validation.auto_fixer import classify_exceptions
    from backend.confidence.scorer import score_extraction

    if correction_log is None:
        correction_log = []

    val_result = ValidationEngine().validate(
        form_type, 
        flat_data, 
        context=context, 
        human_verified_fields=human_verified_fields
    )

    escalated = (context or {}).get("workflow", {}).get("escalated_exceptions", [])
    if escalated:
        filtered_exceptions = []
        for exc in val_result.get("exceptions", []):
            code = exc.get("code")
            field = exc.get("field")
            is_escalated = False
            for e in escalated:
                if e.get("code") == code and e.get("field") == field:
                    is_escalated = True
                    break
            
            if not is_escalated:
                filtered_exceptions.append(exc)
                
        val_result["exceptions"] = filtered_exceptions

    fixable_exceptions, review_exceptions = classify_exceptions(
        exceptions=val_result["exceptions"],
        flat_data=flat_data,
        form_type=form_type,
    )

    confidence_result = score_extraction(
        form_type=form_type,
        flat_data=flat_data,
        exceptions=val_result["exceptions"],
        correction_log=correction_log,
        pdf_type=pdf_type,
        human_verified_fields=human_verified_fields,
    )

    return {
        "val_result":         val_result,
        "fixable_exceptions": fixable_exceptions,
        "review_exceptions":  review_exceptions,
        "confidence_result":  confidence_result,
    }


def build_validation_response(
    form_type: str,
    pdf_type: str,
    data: Any,
    pipeline_result: dict,
    human_verified_fields: list,
    extra: dict | None = None,
) -> dict:
    """
    Build the standard validation response dict shared by /validate,
    /apply-fixes, and /revalidate.

    Args:
        form_type:             IRS form type string.
        pdf_type:              "digital" or "scanned".
        data:                  The (possibly corrected) nested data dict.
        pipeline_result:       Output of run_validation_pipeline().
        human_verified_fields: Fields confirmed by a human.
        extra:                 Optional dict of additional top-level keys
                               (e.g. fixes_applied, latency).

    Returns:
        Response dict ready to pass to jsonify().
    """
    val_result        = pipeline_result["val_result"]
    fixable           = pipeline_result["fixable_exceptions"]
    review            = pipeline_result["review_exceptions"]
    confidence_result = pipeline_result["confidence_result"]

    response = {
        "form_type":             form_type,
        "pdf_type":              pdf_type,
        "confidence":            val_result["confidence"],
        "errors":                val_result["errors"],
        "exceptions":            val_result["exceptions"],
        "summary":               val_result.get("summary", {}),
        "fixable_exceptions":    fixable,
        "review_exceptions":     review,
        "data":                  data,
        "field_confidence":      confidence_result["field_scores"],
        "document_confidence":   confidence_result["document_confidence"],
        "needs_review":          confidence_result["needs_review"],
        "review_fields":         confidence_result["review_fields"],
        "human_verified_fields": human_verified_fields,
    }

    if extra:
        response.update(extra)

    return response
