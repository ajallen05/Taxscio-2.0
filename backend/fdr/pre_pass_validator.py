"""
backend/fdr/pre_pass_validator.py  —  Layer 1: Pre-Pass Validator

Runs before any rules.  Operates on the flat 1040 dict.
Purpose: catch mathematically impossible values that would cause false rule
outputs.  Marks affected fields as unreliable so downstream layers skip them.

Returns:
    reliability_map : {field_name: "reliable" | "unreliable" | "needs_override"}
    flags           : list[PrePassFlag]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PrePassFlag:
    fields:   List[str]
    reason:   str
    severity: str   # "unreliable" | "needs_override" | "investigate"


def run(flat_data: Dict[str, Any]) -> Tuple[Dict[str, str], List[PrePassFlag]]:
    """
    Returns:
        reliability_map  — every field key tagged with a reliability label
        flags            — human-readable list of pre-pass findings
    """
    reliability_map: Dict[str, str] = {}
    flags: List[PrePassFlag] = []

    def _f(key: str) -> Optional[float]:
        """Safe float extraction from flat_data."""
        v = flat_data.get(key)
        if v is None:
            return None
        if isinstance(v, bool):
            return float(v)
        try:
            return float(str(v).replace(",", "").replace("$", "").strip())
        except (ValueError, TypeError):
            return None

    def _mark(field_names: List[str], severity: str, reason: str) -> None:
        for fn in field_names:
            reliability_map[fn] = severity
        flags.append(PrePassFlag(fields=field_names, reason=reason, severity=severity))

    # ── Check 1: qualified dividends > ordinary dividends ─────────────────────
    q_div = _f("line_3a_qualified_dividends")
    o_div = _f("line_3b_ordinary_dividends")
    if q_div is not None and o_div is not None and q_div > o_div:
        _mark(
            ["line_3a_qualified_dividends", "line_3b_ordinary_dividends"],
            "unreliable",
            f"Qualified dividends ({q_div}) cannot exceed ordinary dividends ({o_div}) — "
            "extraction likely mis-mapped these two fields",
        )

    # ── Check 2: taxable IRA amount > gross IRA ───────────────────────────────
    ira_gross = _f("line_4a_ira_distributions")
    ira_tax   = _f("line_4b_taxable_amount")
    if ira_gross is not None and ira_tax is not None and ira_tax > ira_gross:
        _mark(
            ["line_4a_ira_distributions", "line_4b_taxable_amount"],
            "unreliable",
            f"Taxable IRA amount ({ira_tax}) cannot exceed gross distributions ({ira_gross})",
        )

    # ── Check 3: taxable SS > gross SS ────────────────────────────────────────
    ss_gross = _f("line_6a_social_security_benefits")
    ss_tax   = _f("line_6b_taxable_amount")
    if ss_gross is not None and ss_tax is not None and ss_tax > ss_gross:
        _mark(
            ["line_6a_social_security_benefits", "line_6b_taxable_amount"],
            "unreliable",
            f"Taxable SS benefits ({ss_tax}) cannot exceed gross benefits ({ss_gross})",
        )

    # ── Check 4: withholding > 40% of wages (suspicious) ─────────────────────
    wages       = _f("line_1a_total_wages")
    withholding = _f("line_25a_federal_income_tax_withheld_w2")
    if wages and wages > 0 and withholding is not None and withholding > wages * 0.40:
        _mark(
            ["line_25a_federal_income_tax_withheld_w2"],
            "investigate",
            f"Federal withholding ({withholding:.0f}) exceeds 40% of wages ({wages:.0f}) — "
            "verify W-2 withholding field; may indicate extraction error",
        )

    # ── Check 5: additional CTC > child tax credit ────────────────────────────
    ctc  = _f("line_19_child_tax_credit")
    actc = _f("line_28_additional_child_tax_credit")
    if ctc is not None and actc is not None and ctc > 0 and actc > ctc:
        _mark(
            ["line_28_additional_child_tax_credit"],
            "investigate",
            f"Additional CTC ({actc}) exceeds child tax credit ({ctc}) — unusual; verify both lines",
        )

    # ── Check 6: AOC exceeds statutory maximum ($2,500) ──────────────────────
    aoc = _f("line_29_american_opportunity_credit")
    if aoc is not None and aoc > 2500:
        _mark(
            ["line_29_american_opportunity_credit"],
            "unreliable",
            f"American Opportunity Credit ({aoc}) exceeds statutory maximum of $2,500 — "
            "extraction error likely",
        )

    # ── Check 7: capital gain = 0 but digital assets reported ────────────────
    cap_gain      = _f("line_7_capital_gain_loss")
    digital_raw   = flat_data.get("received_or_sold_digital_assets")
    digital_yes   = isinstance(digital_raw, str) and digital_raw.strip().upper() in (
        "YES", "Y", "TRUE", "1"
    )
    if cap_gain is not None and cap_gain == 0 and digital_yes:
        _mark(
            ["line_7_capital_gain_loss"],
            "needs_override",
            "Capital gain/loss is zero but digital assets were reported — "
            "Form 8949 may still be required; conflict_resolver will evaluate",
        )

    # ── Fill remaining fields as reliable ────────────────────────────────────
    for key in flat_data:
        reliability_map.setdefault(key, "reliable")

    return reliability_map, flags
