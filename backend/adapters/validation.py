"""
backend/adapters/validation.py
==============================
Adapter wrapping engine.py for future extraction as the Data Integrity Engine
microservice.

engine.py is IMMUTABLE — zero changes are made to the underlying 90+ IRS
rules.  This adapter wraps the engine and provides the seam.  When the Data
Integrity Engine is extracted, engine.py is copied into that service unchanged
and this adapter becomes the service's internal interface.
"""

from backend.validation.engine import ValidationEngine as _ValidationEngine


class ValidationAdapter:
    """
    Wraps ValidationEngine for Data Integrity Engine extraction.

    IMMUTABILITY RULE: never pass modified exceptions or data back into
    engine.validate() as if they were fresh inputs.  The engine is pure —
    it validates, it does not mutate.
    """

    def __init__(self):
        self._engine = _ValidationEngine()

    def validate(
        self,
        form_type: str,
        flat_data: dict,
        context: dict = None,
    ) -> dict:
        """
        Run all applicable IRS validation rules for the given form type.

        Args:
            form_type: IRS form type string, e.g. "W-2".
            flat_data: Flat key→value dict from flatten_for_validation().
            context:   Optional contextual metadata (filing status, etc.).

        Returns:
            {exceptions, summary, confidence, errors}
        """
        return self._engine.validate(form_type, flat_data, context=context or {})
