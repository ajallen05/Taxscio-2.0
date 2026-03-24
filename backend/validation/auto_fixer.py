"""
auto_fixer.py
=============
Replaces correction_loop.py entirely.

No LLM. No API calls. No retries.

This module does two things:
  1. classify_exceptions() — splits exceptions into "fixable_by_code" and "needs_human_review"
  2. apply_fixes() — applies a list of user-confirmed fix dicts to flat_data

Called from main.py after ValidationEngine.validate().

HOW IT WORKS:
  After /extract, the response now includes:
    - fixable_exceptions:  exceptions that code can fix deterministically
    - review_exceptions:   exceptions that require a human to supply or confirm a value

  The frontend shows both lists:
    - Fixable: each has a "proposed_value" and "fix_description". User clicks "Apply Fix".
    - Review:  each has an "edit_hint". User types a corrected value into an input field.

  When the user approves fixes (any combination), the frontend POSTs to /apply-fixes:
    { "form_type": "W-2", "data": {...}, "fixes": [{"field": "...", "new_value": ...}] }

  /apply-fixes runs apply_fixes() then re-runs ValidationEngine, returns a fresh response.

FIXABLE EXCEPTION CODES (deterministic code can compute the correct value):
  FLD_ZERO_VS_BLANK      — string "0"/"0.0"/"0.00" → convert to float 0.0
  FLD_DASH_SYMBOL        — "—"/"-"/"--" in a field → convert to 0.0
  FLD_NA_TEXT            — "N/A"/"NA"/"N.A." → convert to None
  FLD_CHECKBOX_BLANK     — null boolean → False
  FLD_SPECIAL_CHARS      — OCR noise in numeric field → strip and re-parse
  LLM_OVER_NORMALIZATION — title-cased name → uppercase (IRS standard)
  NUM_SUBTOTAL_MISMATCH  — SS tax/Medicare tax math errors → computed from wages × rate
                           (only when the math formula is unambiguous and wages are present)

REVIEW EXCEPTION CODES (human must supply or confirm the value):
  Everything else with BLOCKING or WARNING severity that has a specific field.
  This includes: missing required fields, invalid SSN/TIN, negative values,
  decimal misplacements, large outliers, invalid distribution codes, etc.
"""

import re
from typing import Any

# ── Constants — Issue 25 (DRY): imported from config.py instead of
# redefining the same values that engine.py already declares.
from backend.config import config as _cfg
SS_RATE        = _cfg.ss_rate        # 0.062
MEDICARE_RATE  = _cfg.medicare_rate  # 0.0145
MATH_TOLERANCE = _cfg.math_tolerance # 1.00

# Codes where code can compute a deterministic correct value
_FIXABLE_CODES = frozenset({
    "FLD_ZERO_VS_BLANK",
    "FLD_DASH_SYMBOL",
    "FLD_NA_TEXT",
    "FLD_CHECKBOX_BLANK",
    "FLD_SPECIAL_CHARS",
    "LLM_OVER_NORMALIZATION",
    "NUM_SUBTOTAL_MISMATCH",   # only for SS/Medicare math — checked at runtime
})

# Codes where human must provide the value
# (field= is set, but code cannot know the correct value)
_REVIEW_CODES = frozenset({
    "FLD_ZERO_VS_BLANK",        # when value=None (required field truly missing)
    "NUM_NEGATIVE_VALUE",
    "NUM_DECIMAL_MISPLACE",
    "NUM_LARGE_OUTLIER",
    "NUM_WITHHOLDING_GT_INC",
    "NUM_DUPLICATE_ENTRY",
    "ID_INVALID_SSN",
    "ID_INVALID_TIN",
    "ID_MASKED_SSN",
    "ID_DUPLICATE_DEP_SSN",
    "FORM_INVALID_CODE",
    "FLD_ILLEGIBLE",
    "FLD_ADDRESS_COLLAPSED",
    "NUM_SUBTOTAL_MISMATCH",   # for non-math mismatches (K-1, monthly sums, etc.)
})

# Human-readable hints shown in the frontend input field per code
_EDIT_HINTS = {
    "FLD_ZERO_VS_BLANK":       "This required field is missing. Enter the value exactly as printed on the form.",
    "NUM_NEGATIVE_VALUE":      "This field should not be negative. Enter the correct positive value (or 0).",
    "NUM_DECIMAL_MISPLACE":    "This value may have a misplaced decimal. Verify against the original document and enter the correct number.",
    "NUM_LARGE_OUTLIER":       "This value is unusually large. Confirm it is correct, or enter the corrected value.",
    "NUM_WITHHOLDING_GT_INC":  "Withholding exceeds income. Confirm both values are correct.",
    "NUM_DUPLICATE_ENTRY":     "This value appears duplicated across fields. Verify and enter the correct value.",
    "ID_INVALID_SSN":          "Enter the SSN in format XXX-XX-XXXX (e.g. 123-45-6789).",
    "ID_INVALID_TIN":          "Enter the TIN/EIN in format XX-XXXXXXX (e.g. 12-3456789).",
    "ID_MASKED_SSN":           "SSN is masked on the document. If you have the full SSN, enter it here.",
    "ID_DUPLICATE_DEP_SSN":    "This SSN matches a dependent record. Verify this is the correct SSN for this taxpayer.",
    "FORM_INVALID_CODE":       "Enter a valid IRS distribution code (e.g. 1, 2, 7, G). See 1099-R Box 7 instructions.",
    "FLD_ILLEGIBLE":           "This field was unreadable by OCR. Enter the value exactly as printed on the original document.",
    "FLD_ADDRESS_COLLAPSED":   "Address appears collapsed onto one line. Enter the full address with proper line breaks.",
    "NUM_SUBTOTAL_MISMATCH":   "The totals do not match. Review both values and enter the correct figure.",
}


# ── Internal fix computers ────────────────────────────────────────────────────

def _compute_fix(exception: dict, flat_data: dict) -> tuple[Any, str] | None:
    """
    Attempt to compute a deterministic fix for an exception.

    Returns (proposed_value, fix_description) or None if not auto-fixable.

    The distinction between fixable and review for FLD_ZERO_VS_BLANK:
      - If value is "0", "0.00" etc → fixable (convert to float 0)
      - If value is None → review (required field missing, human must supply)

    The distinction for NUM_SUBTOTAL_MISMATCH:
      - SS tax (field contains "social_security_tax") AND ss_wages known → fixable
      - Medicare tax (field contains "medicare_tax") AND med_wages known → fixable
      - Everything else → review
    """
    code  = exception.get("code", "")
    field = exception.get("field", "")
    value = exception.get("value")

    if code == "FLD_ZERO_VS_BLANK":
        if value is not None and str(value).strip() in ("0", "0.0", "0.00"):
            return (0.0, f"Convert string zero '{value}' → numeric 0.0")
        return None  # value=None means missing required field → review

    if code == "FLD_DASH_SYMBOL":
        return (0.0, f"Convert dash symbol '{value}' → numeric 0.0")

    if code == "FLD_NA_TEXT":
        return (None, f"Convert N/A text '{value}' → null (field intentionally blank)")

    if code == "FLD_CHECKBOX_BLANK":
        return (False, f"Set null boolean '{field}' → False (unchecked = False per IRS rules)")

    if code == "FLD_SPECIAL_CHARS":
        if value is not None and isinstance(value, str):
            cleaned = re.sub(r"[^\d.\-\(\)]", "", value.replace(",", "").replace("$", ""))
            try:
                neg = cleaned.startswith("(") and cleaned.endswith(")")
                n = float(cleaned.strip("()"))
                result = -n if neg else n
                return (result, f"Strip OCR noise from '{value}' → {result}")
            except (ValueError, TypeError):
                pass
        return None

    if code == "LLM_OVER_NORMALIZATION":
        if value and isinstance(value, str):
            upper = value.upper()
            return (upper, f"Restore IRS ALL-CAPS convention: '{value}' → '{upper}'")
        return None

    if code == "NUM_SUBTOTAL_MISMATCH":
        # Only auto-fix SS tax and Medicare tax — these have exact IRS formulas
        if field and "social_security_tax" in field:
            ss_wages = (
                flat_data.get("social_security_wages") or
                flat_data.get("box_3_social_security_wages")
            )
            if ss_wages is not None:
                try:
                    correct = round(float(ss_wages) * SS_RATE, 2)
                    return (correct, f"Compute SS tax: ${float(ss_wages):,.2f} × 6.2% = ${correct:,.2f}")
                except (TypeError, ValueError):
                    pass

        if field and "medicare_tax" in field:
            med_wages = (
                flat_data.get("medicare_wages_and_tips") or
                flat_data.get("box_5_medicare_wages_and_tips")
            )
            if med_wages is not None:
                try:
                    correct = round(float(med_wages) * MEDICARE_RATE, 2)
                    return (correct, f"Compute Medicare tax: ${float(med_wages):,.2f} × 1.45% = ${correct:,.2f}")
                except (TypeError, ValueError):
                    pass
        
        # ── 1040 Subtotals ──
        if field == "adjusted_gross_income":
            total = flat_data.get("total_income")
            adj = flat_data.get("adjustments_to_income") or 0.0
            if total is not None:
                try:
                    correct = round(float(total) - float(adj), 2)
                    return (correct, f"Compute AGI: Total Income (${float(total):,.2f}) - Adjustments (${float(adj):,.2f}) = ${correct:,.2f}")
                except (TypeError, ValueError):
                    pass

        if field == "taxable_income":
            agi = flat_data.get("adjusted_gross_income")
            ded = flat_data.get("total_deductions") or 0.0
            if agi is not None:
                try:
                    correct = max(0.0, round(float(agi) - float(ded), 2))
                    return (correct, f"Compute Taxable Income: max(0, AGI (${float(agi):,.2f}) - Deductions (${float(ded):,.2f})) = ${correct:,.2f}")
                except (TypeError, ValueError):
                    pass

        if field == "total_withholding":
            w2_wh = flat_data.get("withholding_w2") or 0.0
            n99_wh = flat_data.get("withholding_1099") or 0.0
            other_wh = flat_data.get("withholding_other") or 0.0
            if any(x is not None for x in [flat_data.get("withholding_w2"), flat_data.get("withholding_1099"), flat_data.get("withholding_other")]):
                try:
                    correct = round(float(w2_wh) + float(n99_wh) + float(other_wh), 2)
                    return (correct, f"Compute Total Withholding: W-2 + 1099 + Other = ${correct:,.2f}")
                except (TypeError, ValueError):
                    pass

        if field == "amount_owed":
            tax = flat_data.get("total_tax")
            pmt = flat_data.get("total_payments")
            if tax is not None and pmt is not None:
                try:
                    balance = round(float(tax) - float(pmt), 2)
                    if balance > 0:
                        return (balance, f"Compute Amount Owed: Tax (${float(tax):,.2f}) - Payments (${float(pmt):,.2f}) = ${balance:,.2f}")
                except (TypeError, ValueError):
                    pass

        if field == "overpayment":
            tax = flat_data.get("total_tax")
            pmt = flat_data.get("total_payments")
            if tax is not None and pmt is not None:
                try:
                    balance = round(float(tax) - float(pmt), 2)
                    if balance < 0:
                        correct = abs(balance)
                        return (correct, f"Compute Overpayment: |Tax (${float(tax):,.2f}) - Payments (${float(pmt):,.2f})| = ${correct:,.2f}")
                except (TypeError, ValueError):
                    pass

        # ── K-1 (1065) Subtotals ──
        if field == "total_guaranteed_payments":
            gp_s = flat_data.get("guaranteed_payments_services") or 0.0
            gp_c = flat_data.get("guaranteed_payments_capital") or 0.0
            if any(x is not None for x in [flat_data.get("guaranteed_payments_services"), flat_data.get("guaranteed_payments_capital")]):
                try:
                    correct = round(float(gp_s) + float(gp_c), 2)
                    return (correct, f"Compute Total GP: Services (${float(gp_s):,.2f}) + Capital (${float(gp_c):,.2f}) = ${correct:,.2f}")
                except (TypeError, ValueError):
                    pass

        return None  # other subtotal mismatches → review

    return None


# ── Public API ────────────────────────────────────────────────────────────────

def classify_exceptions(
    exceptions: list,
    flat_data: dict,
    form_type: str
) -> tuple[list, list]:
    """
    Split exceptions into two groups:
      - fixable:      code can compute the correct value deterministically
      - needs_review: human must provide or confirm the value

    Returns:
        (fixable_exceptions: list, review_exceptions: list)

    Each fixable exception has extra keys:
        "proposed_value":    the value that will be written if the user approves
        "fix_description":   human-readable explanation of what the fix does

    Each review exception has extra keys:
        "edit_hint":         instruction shown in the frontend input field
        "current_value":     the current (wrong) value, pre-populated in the input
    """
    fixable      = []
    needs_review = []

    # Track fields we've already classified to avoid double-classifying
    # (an exception can only be in one bucket)
    seen_fields = set()

    for exc in exceptions:
        code     = exc.get("code", "")
        field    = exc.get("field")
        severity = exc.get("severity", "")
        value    = exc.get("value")

        # INFO exceptions with no field are cosmetic — neither bucket
        if severity == "INFO" and not field:
            continue

        # Exceptions with no field are structural/document-level — not user-editable
        if not field:
            continue

        # Avoid duplicate field entries
        dedup_key = (code, field)
        if dedup_key in seen_fields:
            continue
        seen_fields.add(dedup_key)

        # Try to compute a code fix
        fix = _compute_fix(exc, flat_data)
        if fix is not None:
            proposed_value, fix_description = fix
            fixable.append({
                **exc,
                "proposed_value":  proposed_value,
                "fix_description": fix_description,
            })
        elif severity in ("BLOCKING", "WARNING", "CRITICAL"):
            # Has a field, has severity, no code fix → human review
            hint = _EDIT_HINTS.get(code, "Review this field and enter the correct value.")
            needs_review.append({
                **exc,
                "edit_hint":     hint,
                "current_value": value,
            })

    return fixable, needs_review


def apply_fixes(flat_data: dict, fixes: list) -> dict:
    """
    Apply a list of user-confirmed or user-edited fixes to flat_data.

    Args:
        flat_data: the flat dict from flatten_for_validation()
        fixes: list of {"field": str, "new_value": any}
               new_value may be a string from the frontend — coerce numerics.

    Returns:
        updated flat_data dict (copy, original not mutated)
    """
    result = flat_data.copy()

    for fix in fixes:
        field     = fix.get("field")
        new_value = fix.get("new_value")

        if not field:
            continue

        # Coerce string numbers to float (frontend sends everything as strings)
        if isinstance(new_value, str):
            stripped = new_value.strip()
            if stripped == "" or stripped.upper() in ("NULL", "NONE", "N/A"):
                new_value = None
            elif stripped.lower() in ("true", "yes"):
                new_value = True
            elif stripped.lower() in ("false", "no"):
                new_value = False
            else:
                cleaned = re.sub(r"[,$\s]", "", stripped).strip("()")
                try:
                    new_value = float(cleaned)
                    # Convert to int if it's a whole number and the field looks like an integer
                    if new_value == int(new_value) and not any(
                        field.endswith(s) for s in ("_amount", "_income", "_wages", "_tax",
                                                     "_withheld", "_compensation", "_proceeds",
                                                     "_gain", "_loss", "_credit", "_payment",
                                                     "_distribution", "_interest", "_dividends",
                                                     "_benefits", "_contributions", "_deduction")
                    ):
                        new_value = int(new_value)
                except ValueError:
                    pass  # keep as string (e.g. SSN, TIN, name)

        result[field] = new_value

    return result
