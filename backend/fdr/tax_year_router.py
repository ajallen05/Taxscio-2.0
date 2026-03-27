"""
backend/fdr/tax_year_router.py  —  Layer 2: Tax Year Router

Reads tax_year from the extracted JSON and loads the correct rule file.
Falls back to the current active year (2026) for unsupported years.

This keeps the rest of the FDR engine year-agnostic — it never hardcodes years.
"""
from __future__ import annotations

import importlib
import logging
from typing import List

from backend.rules.base_rule_schema import FormRule

log = logging.getLogger("Taxscio.fdr.tax_year_router")

_SUPPORTED_YEARS: set[int] = {2024, 2025, 2026}
_DEFAULT_YEAR = 2026


def load_rules(tax_year: int | None) -> tuple[List[FormRule], str]:
    """
    Load the correct rule set for the given tax year.

    Args:
        tax_year: Tax year from the extracted 1040 JSON.
                  None → defaults to current active year.

    Returns:
        (rules, year_label) — the FormRule list and a string label
        for the fdr_summary.
    """
    if tax_year is None:
        year = _DEFAULT_YEAR
        log.warning("tax_year missing from extracted JSON — defaulting to %s", year)
    elif int(tax_year) not in _SUPPORTED_YEARS:
        year = _DEFAULT_YEAR
        log.warning(
            "tax_year %s not in supported set %s — defaulting to %s",
            tax_year, _SUPPORTED_YEARS, year,
        )
    else:
        year = int(tax_year)

    module_name = f"backend.rules.rules_1040_{year}"
    try:
        module = importlib.import_module(module_name)
        rules: List[FormRule] = module.RULES
        log.info("Loaded %d rules for tax year %s", len(rules), year)
        return rules, str(year)
    except (ImportError, AttributeError) as exc:
        log.error("Failed to import %s: %s — returning empty rule set", module_name, exc)
        return [], str(year)
