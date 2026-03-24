"""
scorer.py
=========
Stage 5 of the pipeline. Assigns a per-field confidence score (0.0–1.0)
to every extracted field, based on:
  - Document type (digital = higher base, scanned = lower)
  - Whether the field passed validation clean
  - Whether it had a WARNING exception
  - Whether a BLOCKING exception was corrected
  - Whether correction failed (field goes to review queue)
  - Whether the field is null (not found by extraction)

Review threshold: fields with score < 0.75 are flagged for human review.
Document confidence: mean of all field scores.
needs_review: True if doc_confidence < 0.85 OR any field score < 0.75.
"""


def score_extraction(
    form_type: str,
    flat_data: dict,
    exceptions: list,
    correction_log: list,
    pdf_type: str,
    human_verified_fields: list = None
) -> dict:
    """
    Compute per-field confidence scores for an extraction result.

    Args:
        form_type:      IRS form type string (unused currently, reserved for
                        form-specific score adjustments in future).
        flat_data:      Flat key-value dict from flatten_for_validation().
        exceptions:     Final exceptions list (post-correction) from ValidationEngine.
        correction_log: correction_log from run_correction_loop() (may be []).
        pdf_type:       "digital" or "scanned".

    Returns:
        {
            "field_scores":         {"field_name": 0.97, ...},
            "document_confidence":  0.94,
            "needs_review":         False,
            "review_fields":        []
        }
    """
    human_verified_fields = set(human_verified_fields or [])
    
    # Build lookup sets from exceptions and correction log
    blocking_fields  = {e["field"] for e in exceptions if e.get("severity") == "BLOCKING" and e.get("field")}
    warning_fields   = {e["field"] for e in exceptions if e.get("severity") == "WARNING"  and e.get("field")}
    corrected_fields = {c["field"] for c in correction_log if c.get("status") == "corrected"}
    failed_fields    = {c["field"] for c in correction_log if c.get("status") in ("failed", "no_change")}

    # Base confidence by document type
    # Digital PDFs have selectable text → higher base reliability
    # Scanned PDFs go through VLM → inherently less certain
    base = 0.97 if pdf_type == "digital" else 0.91

    field_scores = {}
    for field, value in flat_data.items():
        if field in human_verified_fields:
            # Manually pushed by human — absolute confidence
            score = 1.0
            # print(f"[DEBUG] Field '{field}' boosted to 1.0 due to human verification.")
        elif value is None:
            # Field not found in document — moderate-low confidence
            score = 0.70
        elif field in failed_fields:
            # Correction attempted AND failed → human must resolve
            score = 0.20
        elif field in blocking_fields:
            # Still blocking after correction → needs human
            score = 0.35
        elif field in corrected_fields:
            # Was wrong, now corrected by correction loop
            # Lower than a clean pass because a correction was needed
            score = 0.82
        elif field in warning_fields:
            # Minor issue, but field was extracted
            score = base - 0.10
        else:
            # Clean pass — full base confidence
            score = base

        field_scores[field] = round(score, 2)

    if not field_scores:
        return {
            "field_scores":        {},
            "document_confidence": 0.0,
            "needs_review":        True,
            "review_fields":       []
        }

    doc_confidence = round(sum(field_scores.values()) / len(field_scores), 3)
    review_fields  = [f for f, s in field_scores.items() if s < 0.75]
    needs_review   = doc_confidence < 0.85 or bool(review_fields)

    return {
        "field_scores":        field_scores,
        "document_confidence": doc_confidence,
        "needs_review":        needs_review,
        "review_fields":       review_fields
    }
