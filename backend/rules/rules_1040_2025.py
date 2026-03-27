"""
backend/rules/rules_1040_2025.py
Form Dependency Rules for tax year 2025.

Key differences from 2024:
  - 1099-DA introduced for digital asset broker transactions (effective 2025)
  - 1099-K threshold continued downward (inferred from line_8, rule unchanged)
  - 1099-NEC remains primary for contractor income (unchanged from 2020+)

Flat field names follow flatten_for_validation() output from 1040.json:
  income section    → line_1a_total_wages, line_2b_taxable_interest, ...
  tax_and_credits   → line_19_child_tax_credit, line_20_amount_from_schedule_3, ...
  payments          → line_25a_federal_income_tax_withheld_w2, line_27a_earned_income_credit,
                      line_28_additional_child_tax_credit, line_29_american_opportunity_credit
  filing_status     → single, married_filing_jointly, head_of_household, ...
  digital_assets    → received_or_sold_digital_assets
"""
from __future__ import annotations

from backend.rules.base_rule_schema import FormRule

RULES: list[FormRule] = [

    # ──────────────────────────────────────────────────────────────────────────
    # TIER 1 — directly resolvable from Form 1040 fields
    # ──────────────────────────────────────────────────────────────────────────

    # W-2 — wages
    FormRule(
        form_name="W-2",
        rule_type="A",
        confidence_tier=1,
        field="line_1a_total_wages",
        condition_op=">",
        condition_val=0,
        output_confidence="deterministic",
        trigger_template="Wages reported on line 1a — W-2 required from each employer",
        null_behavior="skip",
    ),

    # W-2 cross-confirmation via withholding
    FormRule(
        form_name="W-2",
        rule_type="A",
        confidence_tier=1,
        field="line_25a_federal_income_tax_withheld_w2",
        condition_op=">",
        condition_val=0,
        output_confidence="deterministic",
        trigger_template="Federal withholding on line 25a — confirms W-2 income even if line 1a is ambiguous",
        null_behavior="skip",
        notes="conflict_resolver Rule 1 will merge this with line_1a trigger",
    ),

    # 1099-INT — taxable interest
    FormRule(
        form_name="1099-INT",
        rule_type="A",
        confidence_tier=1,
        field="line_2b_taxable_interest",
        condition_op=">",
        condition_val=0,
        output_confidence="deterministic",
        trigger_template="Taxable interest on line 2b — 1099-INT required from each paying institution",
        null_behavior="skip",
    ),

    # 1099-INT / 1099-OID — tax-exempt interest
    FormRule(
        form_name="1099-INT",
        rule_type="A",
        confidence_tier=1,
        field="line_2a_tax_exempt_interest",
        condition_op=">",
        condition_val=0,
        output_confidence="deterministic",
        trigger_template="Tax-exempt interest on line 2a — 1099-INT or 1099-OID required",
        null_behavior="skip",
    ),

    # 1099-DIV
    FormRule(
        form_name="1099-DIV",
        rule_type="A",
        confidence_tier=1,
        field="line_3b_ordinary_dividends",
        condition_op=">",
        condition_val=0,
        output_confidence="deterministic",
        trigger_template="Ordinary dividends on line 3b — 1099-DIV required from each paying fund/brokerage",
        null_behavior="skip",
    ),

    # 1099-R — IRA distributions
    FormRule(
        form_name="1099-R",
        rule_type="A",
        confidence_tier=1,
        field="line_4a_ira_distributions",
        condition_op=">",
        condition_val=0,
        output_confidence="deterministic",
        trigger_template="IRA distributions on line 4a — 1099-R required from custodian",
        null_behavior="skip",
    ),

    # 1099-R — pensions and annuities
    FormRule(
        form_name="1099-R",
        rule_type="A",
        confidence_tier=1,
        field="line_5a_pensions_annuities",
        condition_op=">",
        condition_val=0,
        output_confidence="deterministic",
        trigger_template="Pension/annuity income on line 5a — 1099-R required from plan administrator",
        null_behavior="skip",
    ),

    # SSA-1099
    FormRule(
        form_name="SSA-1099",
        rule_type="A",
        confidence_tier=1,
        field="line_6a_social_security_benefits",
        condition_op=">",
        condition_val=0,
        output_confidence="deterministic",
        trigger_template="Social Security benefits on line 6a — SSA-1099 required",
        null_behavior="skip",
    ),

    # Form 8949 + Schedule D — capital gain or loss
    FormRule(
        form_name="FORM-8949",
        rule_type="A",
        confidence_tier=1,
        field="line_7_capital_gain_loss",
        condition_op="!=",
        condition_val=0,
        output_confidence="deterministic",
        trigger_template="Capital gain/loss on line 7 — Form 8949 and Schedule D required",
        null_behavior="flag",
        notes="null_behavior=flag: ambiguous null on scanned doc still raises verify flag",
    ),

    # Form 8949 — digital assets checkbox (Type D)
    FormRule(
        form_name="FORM-8949",
        rule_type="D",
        confidence_tier=1,
        field="received_or_sold_digital_assets",
        condition_op="in",
        condition_val=["YES", "Y", "TRUE", "1"],
        output_confidence="deterministic",
        trigger_template="Digital assets reported as received/sold — Form 8949 required regardless of net gain/loss",
        null_behavior="flag",
        notes="conflict_resolver Rule 3 handles zero-gain override for this case",
    ),

    # 1099-DA — digital asset broker (new for tax year 2025)
    FormRule(
        form_name="1099-DA",
        rule_type="D",
        confidence_tier=1,
        field="received_or_sold_digital_assets",
        condition_op="in",
        condition_val=["YES", "Y", "TRUE", "1"],
        output_confidence="deterministic",
        trigger_template="Digital assets reported — 1099-DA required from digital asset broker (new for 2025)",
        null_behavior="flag",
        notes="1099-DA introduced for tax year 2025; replaces/supplements 1099-B for crypto brokers",
    ),

    # Schedule 8812 — child tax credit
    FormRule(
        form_name="SCHEDULE-8812",
        rule_type="A",
        confidence_tier=1,
        field="line_19_child_tax_credit",
        condition_op=">",
        condition_val=0,
        output_confidence="deterministic",
        trigger_template="Child tax credit on line 19 — Schedule 8812 required",
        null_behavior="skip",
    ),

    # Schedule 8812 — additional child tax credit (line 28)
    FormRule(
        form_name="SCHEDULE-8812",
        rule_type="A",
        confidence_tier=1,
        field="line_28_additional_child_tax_credit",
        condition_op=">",
        condition_val=0,
        output_confidence="deterministic",
        trigger_template="Additional child tax credit on line 28 — Schedule 8812 required",
        null_behavior="skip",
    ),

    # Form 8863 — American Opportunity / Lifetime Learning Credit
    FormRule(
        form_name="FORM-8863",
        rule_type="A",
        confidence_tier=1,
        field="line_29_american_opportunity_credit",
        condition_op=">",
        condition_val=0,
        output_confidence="deterministic",
        trigger_template="Education credit on line 29 — Form 8863 required (AOC or LLC)",
        null_behavior="skip",
    ),

    # 1099-NEC — contractor income inferred from line 8 (other income → Schedule 1)
    FormRule(
        form_name="1099-NEC",
        rule_type="A",
        confidence_tier=1,
        field="line_8_other_income",
        condition_op=">",
        condition_val=0,
        output_confidence="inferred",
        trigger_template="Other income on line 8 — 1099-NEC likely (self-employment/contractor); upload Schedule 1 to confirm",
        null_behavior="skip",
    ),

    # 1099-K — payment platform income inferred from line 8
    FormRule(
        form_name="1099-K",
        rule_type="A",
        confidence_tier=1,
        field="line_8_other_income",
        condition_op=">",
        condition_val=0,
        output_confidence="inferred",
        trigger_template="Other income on line 8 — 1099-K possible (third-party payment networks); upload Schedule 1 to confirm",
        null_behavior="skip",
    ),

    # 1099-MISC — miscellaneous income inferred from line 8
    FormRule(
        form_name="1099-MISC",
        rule_type="A",
        confidence_tier=1,
        field="line_8_other_income",
        condition_op=">",
        condition_val=0,
        output_confidence="inferred",
        trigger_template="Other income on line 8 — 1099-MISC possible (rents, royalties, prizes); upload Schedule 1 to confirm",
        null_behavior="skip",
    ),

    # 1099-B — broker proceeds inferred from capital gain line
    FormRule(
        form_name="1099-B",
        rule_type="A",
        confidence_tier=1,
        field="line_7_capital_gain_loss",
        condition_op="!=",
        condition_val=0,
        output_confidence="inferred",
        trigger_template="Capital gain/loss on line 7 — 1099-B likely from brokerage sales",
        null_behavior="skip",
    ),

]
# Note: FORM-8962 and 1095-A are handled unconditionally in tier2_resolver._ALWAYS_ASK
# because ACA enrollment cannot be determined from Form 1040 alone.
# They appear in every client's checklist as ask_client items.

