"""
backend/adapters/auto_fixer.py
==============================
Adapter wrapping auto_fixer.py for future extraction as the Data Integrity
Engine microservice.

auto_fixer.py replaced the LLM-based correction_loop.py.  It is deterministic
and has no external API calls.  Do not re-introduce LLM correction logic.
"""

from backend.validation.auto_fixer import classify_exceptions, apply_fixes


class AutoFixerAdapter:
    """Wraps auto_fixer.py for Data Integrity Engine extraction."""

    def classify(
        self,
        exceptions: list,
        flat_data: dict,
        form_type: str,
    ) -> tuple[list, list]:
        """
        Split exceptions into fixable (code can compute value) and
        review (human must supply value).

        Returns:
            (fixable_exceptions, review_exceptions)
        """
        return classify_exceptions(
            exceptions=exceptions,
            flat_data=flat_data,
            form_type=form_type,
        )

    def apply(self, flat_data: dict, fixes: list) -> dict:
        """
        Apply a list of user-confirmed fixes to flat_data.

        Args:
            flat_data: Flat dict from flatten_for_validation().
            fixes:     List of {"field": str, "new_value": any}.

        Returns:
            Updated flat_data (copy, original not mutated).
        """
        return apply_fixes(flat_data=flat_data, fixes=fixes)
