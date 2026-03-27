"""
backend/fdr/tier2_resolver.py  —  Layer 6: Tier 2 Resolver (Partial — Immediate)

Runs after the conflict resolver.  Two jobs:

  1. CONDITIONAL Tier 2 — resolve what can be inferred right now without
     supporting schedules.  Triggered by signals already present on Form 1040.

  2. UNCONDITIONAL Tier 2 — always append ask_client items for every 1040
     return.  These forms require supporting schedules or client confirmation
     before they can be confirmed present or absent.
     (K-1s, HSA forms, ACA forms, etc.)

Deferred items are marked with action="ask_client" and confidence="unresolvable".
When a supporting schedule later arrives, a partial re-run evaluates only the
deferred items without re-running Tier 1.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.fdr.tier1_resolver import ChecklistEntry

log = logging.getLogger("Taxscio.fdr.tier2_resolver")

# Forms that are ALWAYS asked for every 1040 filer (cannot be confirmed from
# the 1040 alone — need Schedule E, Schedule 1, or client confirmation).
_ALWAYS_ASK: list[tuple[str, str]] = [
    ("1099-SA",    "HSA distribution — 1099-SA required if Health Savings Account was used; upload Schedule 1 to confirm"),
    ("FORM-8889",  "HSA contribution/distribution — Form 8889 required if HSA was used; upload Schedule 1 to confirm"),
    ("K-1 (1065)", "Partnership income — K-1 (1065) required if partner in a partnership; upload Schedule E to confirm"),
    ("K-1 (1120S)","S-Corp income — K-1 (1120S) required if shareholder in an S-Corp; upload Schedule E to confirm"),
    ("K-1 (1041)", "Estate/trust income — K-1 (1041) required if beneficiary of estate/trust; upload Schedule E to confirm"),
    # ACA marketplace forms: 1095-A and 8962 are always asked because ACA enrollment
    # cannot be determined from Form 1040 alone (no dedicated line; hidden in Schedule 3).
    ("1095-A",     "ACA marketplace insurance — 1095-A required if health coverage was purchased through HealthCare.gov"),
    ("FORM-8962",  "Premium Tax Credit — Form 8962 required if ACA marketplace plan was used; verify with client or upload 1095-A"),
]


def run(
    tier1_entries: List[ChecklistEntry],
    flat_data:     Dict[str, Any],
    null_map:      dict,
    tax_year:      int,
) -> List[ChecklistEntry]:
    """
    Augment the Tier 1 entry list with Tier 2 inferred and always-ask items.

    Args:
        tier1_entries: Output of conflict_resolver.run() — already deduplicated.
        flat_data:     Flat 1040 dict.
        null_map:      From null_classifier.build_null_map().
        tax_year:      Integer tax year.

    Returns:
        Combined list of entries (Tier 1 + Tier 2).
    """
    by_form: Dict[str, ChecklistEntry] = {e.form_name: e for e in tier1_entries}

    # ── Conditional Tier 2 ────────────────────────────────────────────────────

    # line_20 (amount from Schedule 3) → flag 8962 / 1095-A if not already present
    sched3 = _f(flat_data, "line_20_amount_from_schedule_3")
    if sched3 and sched3 > 0:
        if "FORM-8962" not in by_form:
            by_form["FORM-8962"] = ChecklistEntry(
                form_name="FORM-8962",
                confidence="unresolvable",
                trigger_line="line_20_amount_from_schedule_3",
                trigger_value=str(int(sched3)),
                action="ask_client",
                reason="Amount from Schedule 3 — Form 8962 (Premium Tax Credit) possible; verify ACA marketplace coverage",
            )
        if "1095-A" not in by_form:
            by_form["1095-A"] = ChecklistEntry(
                form_name="1095-A",
                confidence="unresolvable",
                trigger_line="line_20_amount_from_schedule_3",
                trigger_value=str(int(sched3)),
                action="ask_client",
                reason="Amount from Schedule 3 — 1095-A required if marketplace health plan was used",
            )

    # line_8 (other income) → Form 8962 / 1095-A also possible via Schedule 1 line 26
    # (already covered by Tier 1 inferred 1099-NEC/K/MISC; no additional entry needed here)

    # ── Unconditional Tier 2 (always-ask) ─────────────────────────────────────
    for form_name, reason in _ALWAYS_ASK:
        if form_name not in by_form:
            by_form[form_name] = ChecklistEntry(
                form_name=form_name,
                confidence="unresolvable",
                trigger_line=None,
                trigger_value=None,
                action="ask_client",
                reason=reason,
            )

    return list(by_form.values())


def _f(flat_data: Dict[str, Any], key: str) -> Optional[float]:
    v = flat_data.get(key)
    if v is None:
        return None
    if isinstance(v, bool):
        return float(v)
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return None
