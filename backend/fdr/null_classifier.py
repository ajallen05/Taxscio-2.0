"""
backend/fdr/null_classifier.py  —  Layer 3: Null Ambiguity Classifier

Solves the blank-vs-unreadable problem.

A null field with confidence 0.70 could mean:
  (A) The form field was genuinely blank (client had no IRA distribution)
  (B) The OCR failed to read a value that was present on the form

The classifier uses three signals to distinguish:
  1. Field value  (null / "0" / numeric)
  2. Field confidence  (from scorer.py — 0.70 is the default for null)
  3. Document type  (digital PDF vs scanned image)

Classification matrix
─────────────────────────────────────────────────────────────
Value   Confidence   DocType    → Classification
─────────────────────────────────────────────────────────────
null    ≥ 0.91       digital    → BLANK
null    ≥ 0.91       scanned    → PROBABLE_BLANK
null    ≥ 0.70       digital    → BLANK  (digital = field literally absent/empty)
null    ≥ 0.70       scanned    → AMBIGUOUS
null    < 0.70       any        → UNREADABLE
"0"/0   any          any        → ZERO
non-zero any         any        → VALUE
─────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class NullClass(str, Enum):
    BLANK          = "BLANK"           # field was definitely empty on the form
    PROBABLE_BLANK = "PROBABLE_BLANK"  # likely empty; slight uncertainty (scanned)
    AMBIGUOUS      = "AMBIGUOUS"       # could be blank or OCR failure (scanned + low conf)
    UNREADABLE     = "UNREADABLE"      # OCR almost certainly failed
    ZERO           = "ZERO"            # explicit zero value
    VALUE          = "VALUE"           # non-zero value present


def classify_field(value: Any, confidence: float, doc_type: str) -> NullClass:
    """Return the NullClass for a single field."""
    if value is not None:
        return _classify_present_value(value)
    # value is None — run ambiguity logic
    if confidence >= 0.91:
        return NullClass.BLANK if doc_type == "digital" else NullClass.PROBABLE_BLANK
    if confidence >= 0.70:
        return NullClass.BLANK if doc_type == "digital" else NullClass.AMBIGUOUS
    return NullClass.UNREADABLE


def _classify_present_value(value: Any) -> NullClass:
    """Classify a non-None value as ZERO or VALUE."""
    if isinstance(value, bool):
        return NullClass.VALUE if value else NullClass.ZERO

    if isinstance(value, (int, float)):
        return NullClass.ZERO if value == 0 else NullClass.VALUE

    if isinstance(value, str):
        stripped = value.strip()
        if stripped in ("", "None", "N/A", "NA"):
            # Treat empty-string as null; the FDR will handle as BLANK-equivalent
            return NullClass.BLANK
        try:
            numeric = float(stripped.replace(",", "").replace("$", "").strip("()"))
            return NullClass.ZERO if numeric == 0 else NullClass.VALUE
        except (ValueError, TypeError):
            # Non-numeric string (e.g. "Yes", "No") — treat as VALUE
            return NullClass.VALUE

    return NullClass.VALUE


def build_null_map(
    flat_data: dict,
    confidence_map: dict,
    doc_type: str,
) -> dict[str, NullClass]:
    """
    Build a {field_name: NullClass} map for the entire flat 1040 dict.

    Args:
        flat_data:      Output of flatten_for_validation().
        confidence_map: Per-field confidence scores from scorer.py.
                        Missing fields default to 0.70 (scorer default for null).
        doc_type:       "digital" or "scanned".
    """
    null_map: dict[str, NullClass] = {}
    for field_name, value in flat_data.items():
        conf = float(confidence_map.get(field_name, 0.70))
        null_map[field_name] = classify_field(value, conf, doc_type)
    return null_map
