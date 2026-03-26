"""
backend/utils/data.py
=====================
Shared data-preparation utilities used by multiple routes.

Moved from backend/main.py so that extracted microservices can import these
helpers without pulling in the entire Flask monolith.

Functions
---------
flatten_for_validation(data)      — flatten nested schema dict to flat key/value dict
normalize_form_type(detected)     — normalise model-returned form name to known schema name
"""

import re
import logging

from backend.utils.schemas import get_available_forms

log = logging.getLogger("Taxscio.utils.data")


def flatten_for_validation(data: dict) -> dict:
    """
    Convert a nested NuExtract result dict into a flat key→value dict
    suitable for ValidationEngine.validate().

    Changes from the original main.py version
    ------------------------------------------
    Issue 4  — LIST FIELD BUG FIXED: list values are no longer silently
               dropped.  A list-of-dicts is expanded with an index prefix
               (box_12_0_code, box_12_0_amount, …).  A list-of-scalars is
               kept under the original key so the engine can inspect it.

    Issue 28 — ALIAS GAP FIXED: payer_tin is now included in the alias table.

    Args:
        data: Nested dict as returned by nuextract_normalizer.normalize().

    Returns:
        Flat dict.  List-valued fields are expanded with index suffixes.
        All string-numeric values are coerced to float.
    """
    flat: dict = {}

    def _flatten(obj: object, prefix: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                # Strip the "box_N_" prefix from field names so the engine
                # can match them by canonical name (e.g. "wages" not "box_1_wages").
                bare_key = re.sub(r'^box_[\da-zA-Z]+_', '', k)
                bare_key = re.sub(r'^box_[\da-zA-Z]+$', '', bare_key)
                full_key = f"{prefix}{bare_key}" if bare_key else f"{prefix}{k}"

                if isinstance(v, dict):
                    _flatten(v, prefix)          # recurse, no extra prefix nesting
                elif isinstance(v, list):
                    # Issue 4: expand lists so validation rules can inspect items
                    if v and isinstance(v[0], dict):
                        # list-of-dicts (e.g. W-2 Box 12 entries, 8949 rows)
                        for i, item in enumerate(v):
                            _flatten(item, prefix=f"{full_key}_{i}_")
                    else:
                        # list-of-scalars (e.g. 1099-K monthly totals)
                        flat[full_key] = v
                else:
                    flat[full_key] = v
        elif isinstance(obj, list):
            # Top-level list (rare but guard against it)
            for i, item in enumerate(obj):
                _flatten(item, prefix=f"item_{i}_")

    _flatten(data)

    # ── Composite: synthesise employee_name from first + last ─────────────────
    first = flat.get("employee_first_name")
    last  = flat.get("employee_last_name")
    if first and last:
        flat["employee_name"] = f"{first} {last}".strip()
    elif first:
        flat["employee_name"] = str(first).strip()
    elif last:
        flat["employee_name"] = str(last).strip()

    # ── Field aliases ─────────────────────────────────────────────────────────
    # Issue 28: payer_tin alias added.
    # Maps schema-specific key names → canonical names expected by engine.py.
    aliases = {
        "wages_tips_other_compensation": "wages_tips_compensation",
        "social_security_tips":          "social_security_tips",
        "allocated_tips":                "allocated_tips",
        "dependent_care_benefits":       "dependent_care_benefits",
        "payer_tax_identification":      "payer_tin",   # Issue 28 — was missing
        "payer_ein":                     "payer_tin",   # alternate schema key
    }
    for old, new in aliases.items():
        if old in flat and old != new:
            flat[new] = flat.pop(old)

    # ── Numeric string coercion ────────────────────────────────────────────────
    # Converts "1,234.56" / "$5000" / "0.00" → float.
    # Does NOT convert SSNs ("123-45-6789"), EINs ("12-3456789"), names.
    _num_re = re.compile(r'^\$?-?[\d,]+\.?\d*$')
    for k in list(flat.keys()):
        v = flat[k]
        if isinstance(v, str):
            stripped = v.strip()
            if _num_re.match(stripped):
                try:
                    flat[k] = float(stripped.replace('$', '').replace(',', ''))
                except ValueError:
                    pass

    return flat


def normalize_form_type(detected_type: str) -> str:
    """
    Normalise a form-type string returned by a model to the canonical name
    that matches a schema file.

    Handles common hallucinations (W2 → W-2, K-1-1065 → K-1 (1065), etc.).

    Args:
        detected_type: Raw string from NuExtract detection.

    Returns:
        Canonical form type string, or the input unchanged if no match found.
    """
    if not detected_type:
        return None
    detected_type = str(detected_type).upper()
    available = get_available_forms()

    # 1. Exact / case-insensitive match
    for f in available:
        if f.upper() == detected_type:
            return f

    # 2. Heuristics for common model hallucinations
    if "K-1" in detected_type or "1065" in detected_type:
        return "K-1 (1065)"
    if "W2" in detected_type or "W-2" in detected_type:
        return "W-2"

    # 3. Substring match
    for f in available:
        if f.upper() in detected_type:
            return f

    log.warning(
        "normalize_form_type: no match for '%s' — returning as-is", detected_type
    )
    return detected_type
