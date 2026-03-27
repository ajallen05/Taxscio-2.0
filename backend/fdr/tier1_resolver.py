"""
backend/fdr/tier1_resolver.py  —  Layer 4: Tier 1 Resolver

Applies form dependency rules to the flat 1040 JSON.
Only operates on fields tagged as "reliable" or "needs_override" in the
reliability_map.  "unreliable" fields are skipped entirely.

Each rule produces at most one ChecklistEntry per form_name.
When multiple rules fire for the same form, the highest-confidence entry wins.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.rules.base_rule_schema import FormRule
from backend.fdr.null_classifier import NullClass

_CONF_ORDER = {"deterministic": 3, "inferred": 2, "unresolvable": 1}


@dataclass
class ChecklistEntry:
    form_name:    str
    confidence:   str            # "deterministic" | "inferred" | "unresolvable"
    trigger_line: Optional[str]  # flat field that triggered this entry
    trigger_value: Optional[str] # string representation of the trigger value
    action:       str            # "required" | "investigate" | "ask_client"
    reason:       str            # human-readable for CPA


def run(
    flat_data:       Dict[str, Any],
    raw_data:        dict,
    rules:           List[FormRule],
    reliability_map: Dict[str, str],
    null_map:        Dict[str, NullClass],
) -> List[ChecklistEntry]:
    """
    Evaluate all Tier 1 rules and return a deduplicated list of ChecklistEntry.

    Args:
        flat_data:       Flattened 1040 dict from flatten_for_validation().
        raw_data:        Original nested 1040 dict (for dependent checks).
        rules:           Loaded from tax_year_router (year-specific).
        reliability_map: From pre_pass_validator.
        null_map:        From null_classifier.build_null_map().
    """
    seen: Dict[str, ChecklistEntry] = {}   # form_name → best entry so far

    for rule in rules:
        if rule.confidence_tier != 1:
            continue

        field_reliability = reliability_map.get(rule.field, "reliable")
        if field_reliability == "unreliable":
            continue

        value     = flat_data.get(rule.field)
        null_cls  = null_map.get(rule.field, NullClass.BLANK)

        # ── Null handling ──────────────────────────────────────────────────
        effective_value = value
        if value is None or null_cls in (NullClass.BLANK, NullClass.PROBABLE_BLANK,
                                          NullClass.AMBIGUOUS, NullClass.UNREADABLE,
                                          NullClass.ZERO):
            if null_cls == NullClass.ZERO:
                effective_value = 0
            elif null_cls in (NullClass.BLANK, NullClass.PROBABLE_BLANK):
                if rule.null_behavior == "skip":
                    continue
                elif rule.null_behavior == "assume_zero":
                    effective_value = 0
                else:  # "flag" — blank on digital is safe to skip for most rules
                    continue
            elif null_cls in (NullClass.AMBIGUOUS, NullClass.UNREADABLE):
                if rule.null_behavior == "skip":
                    continue
                elif rule.null_behavior == "assume_zero":
                    effective_value = 0
                else:  # "flag" — ambiguous null: emit an unresolvable entry
                    entry = ChecklistEntry(
                        form_name=rule.form_name,
                        confidence="unresolvable",
                        trigger_line=rule.field,
                        trigger_value=None,
                        action="ask_client",
                        reason=(
                            f"{rule.trigger_template} "
                            f"[field {rule.field!r} was ambiguous on scanned document — verify with client]"
                        ),
                    )
                    _merge(seen, entry)
                    continue

        # ── Primary condition ──────────────────────────────────────────────
        primary_met = _eval(effective_value, rule.condition_op, rule.condition_val)

        # ── Secondary condition (Type C) ───────────────────────────────────
        if rule.rule_type == "C" and rule.second_field:
            second_value = flat_data.get(rule.second_field)
            second_met   = _eval(second_value, rule.second_condition_op, rule.second_condition_val)
            if not (primary_met and second_met):
                continue
        elif not primary_met:
            continue

        # ── Determine output confidence ────────────────────────────────────
        output_conf = rule.output_confidence
        if field_reliability == "needs_override":
            output_conf = "inferred"   # downgrade: ambiguous situation

        action_map = {
            "deterministic": "required",
            "inferred":      "investigate",
            "unresolvable":  "ask_client",
        }

        entry = ChecklistEntry(
            form_name=rule.form_name,
            confidence=output_conf,
            trigger_line=rule.field,
            trigger_value=_str_value(effective_value),
            action=action_map.get(output_conf, "investigate"),
            reason=rule.trigger_template,
        )
        _merge(seen, entry)

    return list(seen.values())


# ── helpers ────────────────────────────────────────────────────────────────────

def _merge(seen: Dict[str, ChecklistEntry], entry: ChecklistEntry) -> None:
    """Keep only the highest-confidence entry per form_name."""
    existing = seen.get(entry.form_name)
    if existing is None:
        seen[entry.form_name] = entry
        return
    if _CONF_ORDER.get(entry.confidence, 0) > _CONF_ORDER.get(existing.confidence, 0):
        seen[entry.form_name] = entry


def _eval(value: Any, op: str, threshold: Any) -> bool:
    """Evaluate a single condition against a value."""
    if op == "always":
        return True

    if op == "in":
        # Case-insensitive list membership check
        candidates = [str(t).strip().upper() for t in (threshold or [])]
        if value is None:
            return False
        return str(value).strip().upper() in candidates

    if op == "truthy":
        if value is None:
            return False
        return bool(value) and str(value).strip().lower() not in (
            "0", "false", "no", "none", "null", "n/a", ""
        )

    # Numeric comparisons
    numeric = _to_float(value)
    thresh  = _to_float(threshold) if not isinstance(threshold, bool) else threshold

    if op == "==":
        if isinstance(threshold, bool):
            return bool(value) == threshold
        if numeric is not None and thresh is not None:
            return numeric == thresh
        return str(value).strip().lower() == str(threshold).strip().lower()

    if op == "!=":
        if numeric is not None and thresh is not None:
            return numeric != thresh
        return str(value).strip().lower() != str(threshold).strip().lower()

    if numeric is None or thresh is None:
        return False

    if op == ">":  return numeric > thresh
    if op == ">=": return numeric >= thresh
    if op == "<":  return numeric < thresh
    if op == "<=": return numeric <= thresh

    return False


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None   # don't coerce booleans to numbers for numeric ops
    if isinstance(value, (int, float)):
        return float(value)
    try:
        s = str(value).replace(",", "").replace("$", "").strip()
        neg = s.startswith("(") and s.endswith(")")
        s2 = s.strip("()")
        return -float(s2) if neg else float(s2)
    except (ValueError, TypeError):
        return None


def _str_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    f = _to_float(value)
    if f is not None:
        return str(int(f)) if f == int(f) else str(f)
    return str(value).strip()
