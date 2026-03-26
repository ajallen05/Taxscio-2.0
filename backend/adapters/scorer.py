"""
backend/adapters/scorer.py
===========================
Adapter wrapping scorer.py for future extraction as the Data Integrity Engine
microservice.

The scorer assigns per-field confidence scores and makes the human-review
routing decision.  It is a pure function — no external calls, no state.
"""

from backend.confidence.scorer import score_extraction


class ScorerAdapter:
    """Wraps scorer.py for Data Integrity Engine extraction."""

    def score(
        self,
        form_type: str,
        flat_data: dict,
        exceptions: list,
        pdf_type: str,
        correction_log: list = None,
        human_verified_fields: list = None,
    ) -> dict:
        """
        Compute per-field and document-level confidence scores.

        Args:
            form_type:             IRS form type string.
            flat_data:             Flat dict from flatten_for_validation().
            exceptions:            Final exceptions list from ValidationEngine.
            pdf_type:              "digital" or "scanned".
            correction_log:        Correction log (empty list for human edits).
            human_verified_fields: Fields confirmed by a human (score = 1.0).

        Returns:
            {field_scores, document_confidence, needs_review, review_fields}
        """
        return score_extraction(
            form_type=form_type,
            flat_data=flat_data,
            exceptions=exceptions,
            correction_log=correction_log or [],
            pdf_type=pdf_type,
            human_verified_fields=human_verified_fields or [],
        )
