"""
backend/rules/base_rule_schema.py
Dataclass that defines the shape of a single Form Dependency Rule.
Every rule file (rules_1040_YYYY.py) returns a list of FormRule instances.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

RuleType = Literal["A", "B", "C", "D"]
OutputConfidence = Literal["deterministic", "inferred", "unresolvable"]
NullBehavior = Literal["skip", "flag", "assume_zero"]


@dataclass
class FormRule:
    # ── identity ──────────────────────────────────────────────────────────────
    form_name: str                   # e.g. "W-2", "FORM-8949", "SCHEDULE-8812"
    rule_type: RuleType              # A=direct, B=threshold, C=combination, D=special
    confidence_tier: int             # 1 = resolvable from 1040 alone; 2 = needs supporting doc

    # ── primary trigger ───────────────────────────────────────────────────────
    field: str                       # flat field name from flatten_for_validation()
    condition_op: str                # ">", ">=", "<", "<=", "==", "!=", "truthy", "in", "always"
    condition_val: Any               # threshold / list for "in" / None for "always"

    # ── output ────────────────────────────────────────────────────────────────
    output_confidence: OutputConfidence
    trigger_template: str            # human-readable reason for the CPA
    null_behavior: NullBehavior      # what to do when field is null

    # ── optional second condition (Type C) ────────────────────────────────────
    second_field: Optional[str] = None
    second_condition_op: Optional[str] = None
    second_condition_val: Any = None

    # ── notes (developer commentary) ─────────────────────────────────────────
    notes: str = ""
