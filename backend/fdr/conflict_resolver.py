"""
backend/fdr/conflict_resolver.py  —  Layer 5: Cross-Form Conflict Resolver

Runs after Tier 1.  Modifies the Tier 1 output before writing to DB.

Eight conflict rules (per architecture spec):
  Rule 1 — W-2 + withholding cross-confirm
  Rule 2 — 1099-DIV internal consistency (handled by pre_pass; no-op here)
  Rule 3 — Form 8949 zero-gain digital-asset override
  Rule 4 — 1099-NEC/K/MISC tax year split (handled by rule files; no-op here)
  Rule 5 — 1099-R rollover suppression note
  Rule 6 — K-1 (1041) income suppression note
  Rule 7 — Schedule 8812 dependent consistency check
  Rule 8 — HOH + EIC dependent consistency check
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.fdr.tier1_resolver import ChecklistEntry

log = logging.getLogger("Taxscio.fdr.conflict_resolver")


def run(
    entries:    List[ChecklistEntry],
    flat_data:  Dict[str, Any],
    raw_data:   dict,
    tax_year:   int,
) -> tuple[List[ChecklistEntry], List[str]]:
    """
    Apply conflict rules to the Tier 1 output.

    Args:
        entries:   Mutable list of ChecklistEntry from tier1_resolver.
        flat_data: Flat 1040 dict.
        raw_data:  Original nested 1040 dict (for dependent array access).
        tax_year:  Integer tax year (for Rule 4 tax-year-specific branching).

    Returns:
        (updated_entries, conflict_notes) — modified entries + human-readable notes
    """
    by_form: Dict[str, ChecklistEntry] = {e.form_name: e for e in entries}
    notes: List[str] = []

    def _f(key: str) -> Optional[float]:
        v = flat_data.get(key)
        if v is None:
            return None
        if isinstance(v, bool):
            return float(v)
        try:
            return float(str(v).replace(",", "").replace("$", "").strip())
        except (ValueError, TypeError):
            return None

    dependents = raw_data.get("dependents") or []

    # ── Rule 1: W-2 + withholding cross-confirm ────────────────────────────────
    wages       = _f("line_1a_total_wages")
    withholding = _f("line_25a_federal_income_tax_withheld_w2")
    w2_entry    = by_form.get("W-2")

    if w2_entry is None and withholding and withholding > 0:
        # Withholding alone proves W-2 exists even if line_1a is null/unreliable
        by_form["W-2"] = ChecklistEntry(
            form_name="W-2",
            confidence="deterministic",
            trigger_line="line_25a_federal_income_tax_withheld_w2",
            trigger_value=str(int(withholding)) if withholding == int(withholding) else str(withholding),
            action="required",
            reason="Federal withholding on line 25a proves W-2 exists — required",
        )
        notes.append("Rule 1: W-2 added from withholding evidence (line_1a was absent/zero)")

    elif w2_entry and wages and wages > 0 and (withholding is None or withholding == 0):
        w2_entry.reason += " — note: no federal withholding on line 25a; verify W-2 withholding box"
        notes.append("Rule 1: W-2 confirmed from wages but withholding is zero — annotated")

    # ── Rule 3: Form 8949 zero-gain digital-asset override ────────────────────
    cap_gain   = _f("line_7_capital_gain_loss")
    digital_v  = flat_data.get("received_or_sold_digital_assets")
    digital_yes = (
        isinstance(digital_v, str)
        and digital_v.strip().upper() in ("YES", "Y", "TRUE", "1")
    )

    if cap_gain is not None and cap_gain == 0 and digital_yes:
        if "FORM-8949" not in by_form:
            by_form["FORM-8949"] = ChecklistEntry(
                form_name="FORM-8949",
                confidence="deterministic",
                trigger_line="received_or_sold_digital_assets",
                trigger_value="Yes",
                action="required",
                reason=(
                    "Digital assets reported (zero net gain) — Form 8949 still required; "
                    "all disposals must be reported regardless of gain/loss"
                ),
            )
        notes.append("Rule 3: Form 8949 required despite zero cap gain — digital assets override applied")

    # ── Rule 5: 1099-R rollover suppression note ───────────────────────────────
    ira_gross = _f("line_4a_ira_distributions")
    ira_tax   = _f("line_4b_taxable_amount")
    r_entry   = by_form.get("1099-R")
    if r_entry and ira_gross and ira_gross > 0 and ira_tax is not None and ira_tax == 0:
        r_entry.reason += (
            " — taxable amount (line 4b) is zero; likely a direct rollover — "
            "1099-R still required; confirm rollover treatment"
        )
        notes.append("Rule 5: 1099-R annotated as probable rollover (4b = 0)")

    # ── Rule 6: K-1 (1041) income suppression note ────────────────────────────
    # If Schedule E (Tier 2 deferred) produces a K-1 (1041), annotate interest/
    # dividend entries to say the source may be the estate/trust, not separate 1099s.
    # (Full resolution happens in tier2_resolver; here we just record the note.)

    # ── Rule 7: Schedule 8812 dependent consistency ────────────────────────────
    ctc        = _f("line_19_child_tax_credit")
    sched_8812 = by_form.get("SCHEDULE-8812")
    if sched_8812 and ctc and ctc > 0:
        has_ctc_dep = any(d.get("child_tax_credit") for d in dependents)
        has_cod_dep = any(d.get("credit_for_other_dependents") for d in dependents)
        if not dependents:
            sched_8812.reason += (
                " — WARNING: child tax credit claimed but no dependents found in extraction; "
                "verify dependent section was correctly extracted"
            )
            notes.append("Rule 7: Schedule 8812 CTC claimed but no dependents extracted — inconsistency flagged")
        elif has_ctc_dep or has_cod_dep:
            notes.append("Rule 7: Schedule 8812 consistent with dependent CTC/COD flags")
        else:
            sched_8812.reason += (
                " — note: dependent records present but no child_tax_credit or "
                "credit_for_other_dependents flag set; verify dependent eligibility"
            )
            notes.append("Rule 7: Schedule 8812 — dependent present but CTC flag not set in extraction")

    # ── Rule 8: HOH + EIC dependent consistency ────────────────────────────────
    hoh = flat_data.get("head_of_household")
    eic = _f("line_27a_earned_income_credit")
    hoh_active = (
        hoh is True
        or (isinstance(hoh, str) and hoh.strip().lower() in ("true", "yes", "1"))
    )
    if hoh_active and eic and eic > 0:
        if not dependents or not any(d.get("first_name") for d in dependents):
            notes.append(
                "Rule 8: HOH filing status + EIC claimed but no dependent found — "
                "extraction may have missed the dependent section; verify before filing"
            )
        else:
            notes.append("Rule 8: HOH + EIC consistent — qualifying person found in dependent list")

    return list(by_form.values()), notes
