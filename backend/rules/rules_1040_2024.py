"""
backend/rules/rules_1040_2024.py
Form Dependency Rules for tax year 2024.

Differences from 2025:
  - No 1099-DA (digital asset broker form not yet required for 2024 tax year)
  - All other rules identical to 2025
"""
from __future__ import annotations

from backend.rules.rules_1040_2025 import RULES as _RULES_2025
from backend.rules.base_rule_schema import FormRule

# 2024: exclude 1099-DA (introduced for tax year 2025)
RULES: list[FormRule] = [r for r in _RULES_2025 if r.form_name != "1099-DA"]
