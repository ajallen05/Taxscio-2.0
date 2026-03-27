"""
backend/rules/rules_1040_2026.py
Form Dependency Rules for tax year 2026 (current active year).

Currently identical to 2025 — 1099-DA second year of reporting.
Add year-specific overrides here when IRS rule changes are published.
"""
from __future__ import annotations

from backend.rules.rules_1040_2025 import RULES as _RULES_2025
from backend.rules.base_rule_schema import FormRule

RULES: list[FormRule] = list(_RULES_2025)
