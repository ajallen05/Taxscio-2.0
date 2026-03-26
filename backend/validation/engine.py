import re
import hashlib
from typing import Any

MATH_TOLERANCE = 1.00
K1_TOLERANCE   = 5.00
CURRENT_TAX_YEAR = 2026

SS_RATE              = 0.062
MEDICARE_RATE        = 0.0145
SS_WAGE_BASE         = 168600.00
MAX_SS_TAX           = 10453.20
DEP_CARE_LIMIT       = 5000.00
BACKUP_WITHHOLDING_RATE = 0.24

STANDARD_DEDUCTIONS_2026 = {
    "single": 14600.0, "married filing jointly": 29200.0,
    "married filing separately": 14600.0, "head of household": 21900.0,
    "qualifying surviving spouse": 29200.0,
    "mfj": 29200.0, "mfs": 14600.0, "hoh": 21900.0, "qss": 29200.0
}

VALID_1099R_CODES = {'1.0','2.0','3.0','4.0','5.0','6.0','7.0','8.0','9.0',
    '1','2','3','4','5','6','7','8','9','A','B','C','D','E',
    'F','G','H','J','K','L','M','N','P','Q','R','S','T','U','W'
}

NUMERIC_FIELD_SUFFIXES = (
    "_amount", "_income", "_wages", "_tax", "_withheld",
    "_compensation", "_proceeds", "_gain", "_loss", "_credit",
    "_payment", "_distribution", "_interest", "_dividends",
    "_royalties", "_benefits", "_contributions", "_deduction"
)

NAME_FIELDS = [
    "employee_name", "employer_name", "payer_name", "recipient_name",
    "taxpayer_name", "partner_name", "shareholder_name", "beneficiary_name",
    "employee_first_name", "employee_last_name", "taxpayer_first_name",
    "taxpayer_last_name", "spouse_first_name", "spouse_last_name",
    "recipient_first_name", "recipient_last_name"
]

INCOME_FIELDS_1099_MISC = [
    "rents", "royalties", "other_income", "fishing_boat_proceeds",
    "medical_health_care_payments", "substitute_payments",
    "crop_insurance_proceeds", "gross_proceeds_attorney",
    "section_409a_deferrals", "excess_golden_parachute",
    "nonqualified_deferred_comp"
]

INVALID_TIN_PREFIXES = {
    '00','07','08','09','17','18','19','28',
    '29','49','69','70','78','79','89'
}

OCR_CONFIDENCE_THRESHOLD       = 0.80
FIELD_CONFIDENCE_THRESHOLD     = 0.70
SPOOFING_RISK_THRESHOLD        = 0.70
EXTRACTION_ATTEMPT_LIMIT       = 10
CONTEXT_WINDOW_TOKEN_LIMIT     = 180000

STATE_FEDERAL_INCOME_CONFLICT_THRESHOLD = 1000.0
NULL_RATIO_WARNING_THRESHOLD            = 0.70
UC_WITHHOLDING_TOLERANCE_RATE          = 0.05
BBOX_PIXEL_DRIFT_THRESHOLD             = 15.0
BBOX_COORD_SPACE                       = "pixels"  # "pixels" or "normalised"

EXCEPTION_REGISTRY = {
    "STR_OPTIONAL_BLANK":       ("Structural", "Optional Field Left Blank", "Mark as NULL_ALLOWED", "INFO"),
    "STR_CONDITIONAL_SKIP":     ("Structural", "Conditional Field Not Triggered", "Evaluate parent rule first", "INFO"),
    "STR_SCHEDULE_MISSING":     ("Structural", "Schedule Not Attached", "Validate threshold logic", "WARNING"),
    "STR_MULTI_PAGE_VARIANT":   ("Structural", "Multi-Page Form Variant", "Validate against version schema", "INFO"),
    "STR_ALT_LAYOUT":           ("Structural", "Alternate Layout Version", "Apply version-aware template", "INFO"),
    "STR_DEPRECATED_FIELD":     ("Structural", "Deprecated Field Present", "Ignore if not required for year", "INFO"),
    "FLD_ZERO_VS_BLANK":        ("Field-Level", "Zero vs Blank", "Enforce strict numeric/null distinction", "BLOCKING"),
    "FLD_DASH_SYMBOL":          ("Field-Level", "Dash Symbol Used", "Normalize to numeric zero", "INFO"),
    "FLD_CHECKBOX_BLANK":       ("Field-Level", "Checkbox Not Checked", "Interpret as FALSE", "INFO"),
    "FLD_NA_TEXT":              ("Field-Level", "N/A Text", "Convert to structured null", "INFO"),
    "FLD_ILLEGIBLE":            ("Field-Level", "Illegible but Present", "Re-run OCR or manual review", "WARNING"),
    "FLD_ADDRESS_COLLAPSED":    ("Field-Level", "Multi-Line Address Collapsed", "Structured re-parse", "WARNING"),
    "FLD_SPECIAL_CHARS":        ("Field-Level", "Special Characters in Numeric Field", "Sanitize before validation", "WARNING"),
    "NUM_SUBTOTAL_MISMATCH":    ("Numeric & Arithmetic", "Subtotal Mismatch", "Recalculate and flag", "WARNING"),
    "NUM_WITHHOLDING_GT_INC":   ("Numeric & Arithmetic", "Withholding > Income", "Mark review_required", "WARNING"),
    "NUM_NEGATIVE_VALUE":       ("Numeric & Arithmetic", "Negative Value Not Allowed", "Hard validation failure", "BLOCKING"),
    "NUM_ROUNDING_VARIANCE":    ("Numeric & Arithmetic", "Rounding Variance", "Accept within tolerance", "INFO"),
    "NUM_DECIMAL_MISPLACE":     ("Numeric & Arithmetic", "Decimal Misplacement", "Cross-field plausibility check", "WARNING"),
    "NUM_LARGE_OUTLIER":        ("Numeric & Arithmetic", "Large Statistical Outlier", "Route to Intelligence layer", "WARNING"),
    "NUM_DUPLICATE_ENTRY":      ("Numeric & Arithmetic", "Duplicate Monetary Entry", "Cross-box validation", "WARNING"),
    "ID_INVALID_SSN":           ("Identity & Entity", "Invalid SSN Format", "Reject document", "BLOCKING"),
    "ID_INVALID_TIN":           ("Identity & Entity", "Invalid TIN Format", "Reject document", "BLOCKING"),
    "ID_MASKED_SSN":            ("Identity & Entity", "Masked SSN", "Accept but flag masked", "WARNING"),
    "ID_NAME_TIN_MISMATCH":     ("Identity & Entity", "Name-TIN Mismatch", "Cross-reference DB", "WARNING"),
    "ID_DUPLICATE_DEP_SSN":     ("Identity & Entity", "Duplicate Dependent SSN", "Reject", "BLOCKING"),
    "ID_NEW_EMPLOYER_TIN":      ("Identity & Entity", "Employer TIN Not Seen Before", "Allow but flag for review", "WARNING"),
    "CTX_FILING_STATUS_DEP":    ("Contextual / Tax Logic", "Filing Status Dependency", "Validate filing status", "BLOCKING"),
    "CTX_CAP_LOSS_MISSING":     ("Contextual / Tax Logic", "Capital Loss Carryover Missing", "Cross-year validation", "WARNING"),
    "CTX_BIZ_NO_SCHED_C":      ("Contextual / Tax Logic", "Business Income Without Schedule C", "Flag anomaly", "WARNING"),
    "CTX_STATE_NO_FED":         ("Contextual / Tax Logic", "State Tax Without Federal Base", "Cross-form validation", "WARNING"),
    "CTX_SPOUSE_SINGLE":        ("Contextual / Tax Logic", "Spouse Document for Single Filing", "Conditional review", "WARNING"),
    "CTX_DEP_FORM":             ("Contextual / Tax Logic", "Dependent Form Uploaded", "Link dependent entity", "WARNING"),
    "OCR_CROPPED":              ("Formatting & OCR", "Cropped Document", "Block extraction", "BLOCKING"),
    "OCR_ROTATED":              ("Formatting & OCR", "Rotated Scan", "Auto-rotate", "INFO"),
    "OCR_LOW_CONFIDENCE":       ("Formatting & OCR", "Low OCR Confidence", "Re-run or manual review", "WARNING"),
    "OCR_MULTI_FORM_PDF":       ("Formatting & OCR", "Multiple Forms in One PDF", "Segment pages", "WARNING"),
    "OCR_DUPLICATE_PAGE":       ("Formatting & OCR", "Duplicate Page", "Page-level hash check", "INFO"),
    "OCR_CORRUPTED_PDF":        ("Formatting & OCR", "Corrupted PDF", "Reject and request re-upload", "BLOCKING"),
    "XDOC_DUPLICATE_UPLOAD":    ("Cross-Document", "Duplicate Form Upload", "Ignore duplicate", "INFO"),
    "XDOC_CONFLICT_INCOME":     ("Cross-Document", "Conflicting Income Across Forms", "Flag CPA review", "WARNING"),
    "XDOC_MISSING_RECURRING":   ("Cross-Document", "Missing Recurring Form", "Intelligence alert", "WARNING"),
    "XDOC_STATE_MISMATCH":      ("Cross-Document", "Mismatched State Income", "Cross-validation", "WARNING"),
    "LLM_HALLUCINATED":         ("LLM Interpretation", "Hallucinated Field", "Validate against OCR anchors", "BLOCKING"),
    "LLM_BLANK_AS_MISSING":     ("LLM Interpretation", "Blank Interpreted as Missing", "Enforce schema null rules", "BLOCKING"),
    "LLM_CONTEXT_DRIFT":        ("LLM Interpretation", "Context Drift", "Bounding-box anchoring", "BLOCKING"),
    "LLM_REORDERED_MAP":        ("LLM Interpretation", "Reordered Field Mapping", "Template coordinate validation", "BLOCKING"),
    "LLM_OVER_INFERENCE":       ("LLM Interpretation", "Over-Inference", "Disable inference mode", "BLOCKING"),
    "LLM_NUMERIC_WORD_ERR":     ("LLM Interpretation", "Numeric Word Conversion Error", "Strict numeric extraction", "WARNING"),
    "LLM_CROSS_PAGE_BLEED":     ("LLM Interpretation", "Cross-Page Context Bleed", "Page-isolated prompts", "BLOCKING"),
    "LLM_OVER_NORMALIZATION":   ("LLM Interpretation", "Over-Normalization", "Preserve raw extracted text", "WARNING"),
    "ENG_UNKNOWN_CLIENT":       ("Engagement Integrity", "Unknown Client", "Route to Unmatched Queue", "BLOCKING"),
    "ENG_INACTIVE":             ("Engagement Integrity", "Inactive Engagement", "Mark pre-engagement", "WARNING"),
    "ENG_WRONG_YEAR":           ("Engagement Integrity", "Wrong Tax Year", "Route to correct workflow", "WARNING"),
    "ENG_DUPLICATE_PROFILE":    ("Engagement Integrity", "Duplicate Client Profile", "Escalate identity resolution", "CRITICAL"),
    "ENG_WRONG_ENTITY":         ("Engagement Integrity", "Wrong Entity Type", "Block and flag", "BLOCKING"),
    "ENG_CLIENT_DELETED":       ("Engagement Integrity", "Client Deleted but Docs Incoming", "Reject and notify", "BLOCKING"),
    "ENG_CLIENT_MERGED":        ("Engagement Integrity", "Client Merged / Renamed", "Maintain alias mapping", "WARNING"),
    "EMAIL_UNKNOWN_SENDER":     ("Email & Source-Level", "Valid Form from Unknown Email", "Validate via SSN", "WARNING"),
    "EMAIL_CPA_FORWARD":        ("Email & Source-Level", "Email Forwarded by CPA", "Match SSN to CPA client list", "INFO"),
    "EMAIL_SPOOFED":            ("Email & Source-Level", "Spoofed Domain", "Risk score + security alert", "CRITICAL"),
    "EMAIL_MULTI_CLIENT":       ("Email & Source-Level", "Multiple Clients in One Email", "Split and match by SSN", "WARNING"),
    "EMAIL_NO_METADATA":        ("Email & Source-Level", "Attachment Without Metadata", "Extract then resolve by SSN", "WARNING"),
    "EMAIL_ENCRYPTED_PDF":      ("Email & Source-Level", "Encrypted PDF", "Trigger password workflow", "WARNING"),
    "MT_CROSS_TENANT_CLIENT":   ("Multi-Tenant", "Client Exists in Another Tenant", "Hard isolation block", "CRITICAL"),
    "MT_CROSS_TENANT_DOC":      ("Multi-Tenant", "Cross-Tenant Document Routing", "Security block + alert", "CRITICAL"),
    "MT_SHARED_FAMILY":         ("Multi-Tenant", "Shared Family Accounts", "Household linking model", "INFO"),
    "WF_AFTER_CLOSED":          ("Workflow State", "Document After Ledger Closed", "Reopen or hold", "WARNING"),
    "WF_REUPLOAD":              ("Workflow State", "Re-upload After Extraction", "Increment version", "INFO"),
    "WF_LEDGER_NOT_UPDATED":    ("Workflow State", "Extraction Completed but Ledger Not Updated", "Orchestrator repair", "BLOCKING"),
    "WF_MANUAL_NO_AUDIT":       ("Workflow State", "Manual Override Without Audit", "Block until logged", "CRITICAL"),
    "CY_WRONG_YEAR_UPLOAD":     ("Cross-Year", "Prior-Year Form Uploaded as Current", "Auto-detect and reroute", "WARNING"),
    "CY_CARRYOVER_MISSING":     ("Cross-Year", "Carryover Expected but Missing", "Intelligence flag", "WARNING"),
    "CY_EST_NOT_FILED":         ("Cross-Year", "Estimated Payments Present but Not Filed", "CPA review trigger", "WARNING"),
    "LED_FORM_NOT_IN_LEDGER":   ("Ledger-Level", "Form Received Not in Ledger", "Add dynamic ledger entry", "WARNING"),
    "LED_CLIENT_WAIVED":        ("Ledger-Level", "Required Form Missing but Client Confirms None", "Mark as waived", "INFO"),
    "LED_MULTIPLE_SAME_FORM":   ("Ledger-Level", "Multiple Instances of Same Form", "Support quantity", "INFO"),
    "LED_PARTIAL_FORM_SET":     ("Ledger-Level", "Partial Form Set", "Block and request full set", "BLOCKING"),
    "DB_JSON_FLATTEN_FAIL":     ("Data Persistence & Schema", "JSON Flatten Failure", "Rollback transaction", "BLOCKING"),
    "DB_TYPE_CONFLICT":         ("Data Persistence & Schema", "Field Type Conflict", "Coerce or reject", "BLOCKING"),
    "DB_NULL_NON_NULLABLE":     ("Data Persistence & Schema", "Null in Non-Nullable Column", "Block insert", "BLOCKING"),
    "DB_DUPLICATE_PK":          ("Data Persistence & Schema", "Duplicate Primary Key", "Idempotent enforcement", "BLOCKING"),
    "DB_SCHEMA_DRIFT":          ("Data Persistence & Schema", "Schema Drift", "Trigger schema review workflow", "WARNING"),
    "SEC_PII_IN_LOGS":          ("Security & Compliance", "PII in Logs", "Mask + alert", "CRITICAL"),
    "SEC_UNAUTHORIZED_ACCESS":  ("Security & Compliance", "Unauthorized Role Access", "Hard fail + audit", "CRITICAL"),
    "SEC_S3_PUBLIC":            ("Security & Compliance", "S3 Public Access Risk", "Security alert", "CRITICAL"),
    "SEC_TAMPERED_DOC":         ("Security & Compliance", "Tampered Document", "Lock and investigate", "CRITICAL"),
    "SEC_EXCESS_ATTEMPTS":      ("Security & Compliance", "Excessive Extraction Attempts", "Rate-limit + alert", "CRITICAL"),
    "LLMD_CROSS_CLIENT_BLEED":  ("LLM-Specific Domain", "Cross-Client Data Bleed", "Stateless extraction", "CRITICAL"),
    "LLMD_CONTEXT_OVERFLOW":    ("LLM-Specific Domain", "Context Window Spillover", "Page isolation", "BLOCKING"),
    "LLMD_MULTI_FORM_MISASSIGN":("LLM-Specific Domain", "Multi-Form PDF Misassignment", "Page segmentation logic", "WARNING"),
}


class ValidationEngine:

    def _make_exc(self, code, description, field=None, value=None):
        cat, exc_name, handling, severity = EXCEPTION_REGISTRY[code]
        return {"code": code, "category": cat, "exception": exc_name,
                "description": description, "severity": severity,
                "handling": handling, "field": field, "value": value}

    def _g(self, ctx, *keys, default=None):
        val = ctx or {}
        for k in keys:
            if not isinstance(val, dict):
                return default
            val = val.get(k, default)
            if val is None:
                return default
        return val

    def _f(self, data, key):
        val = data.get(key)
        if val is None:
            return None
        s = str(val).strip()
        if s.upper() in ("N/A", "NA", "N.A.", "NONE"):
            return None
        if s in ("\u2014", "\u2013", "-", "--"):
            return 0.0
        if s == "":
            return None
        try:
            negative = s.startswith("(") and s.endswith(")")
            s2 = s.strip("()").replace("$", "").replace(",", "").replace("%", "").strip()
            s2 = re.sub(r"[^\d.\-]", "", s2)
            if not s2 or s2 == ".":
                return None
            result = float(s2)
            return -result if negative else result
        except (ValueError, TypeError):
            return None

    def _check_tin(self, tin_str):
        s = str(tin_str).strip()
        if re.match(r"^[\*Xx]{3}-[\*Xx]{2}-\d{4}$", s):
            return None, True
        if re.match(r"^\d{3}-\d{2}-[\*Xx]{4}$", s):
            return None, True
        if re.match(r"^[\*Xx]{3}-[\*Xx]{2}-[\*Xx]{4}$", s):
            return None, True
        m = re.match(r"^(\d{3})-(\d{2})-(\d{4})$", s)
        if m:
            area, group, serial = m.groups()
            if area == "000":
                return f"SSN area '000' is invalid.", False
            if area == "666":
                return f"SSN area '666' is invalid.", False
            if int(area) >= 900:
                return f"SSN area '{area}' (900-999) is reserved.", False
            if group == "00":
                return f"SSN group '00' is invalid.", False
            if serial == "0000":
                return f"SSN serial '0000' is invalid.", False
            return None, False
        m = re.match(r"^(\d{2})-(\d{7})$", s)
        if m:
            prefix = m.group(1)
            if prefix in INVALID_TIN_PREFIXES:
                return f"TIN prefix '{prefix}' is an unassigned IRS prefix.", False
            return None, False
        return f"'{s}' is not valid SSN (XXX-XX-XXXX) or TIN (XX-XXXXXXX).", False

    def _tin_exc(self, d, field, require_tin=False):
        excs = []
        val = d.get(field)
        if val is None:
            return excs
        s = str(val).strip()
        if require_tin:
            if not re.match(r"^\d{2}-\d{7}$", s):
                excs.append(self._make_exc("ID_INVALID_TIN",
                    f"Field '{field}' value '{s}' is not valid TIN format XX-XXXXXXX.",
                    field=field, value=s))
            elif s[:2] in INVALID_TIN_PREFIXES:
                excs.append(self._make_exc("ID_INVALID_TIN",
                    f"TIN prefix '{s[:2]}' is an unassigned IRS prefix.",
                    field=field, value=s))
        else:
            err, masked = self._check_tin(s)
            if masked:
                excs.append(self._make_exc("ID_MASKED_SSN",
                    f"Field '{field}' is masked/redacted: '{s}'.",
                    field=field, value=s))
            elif err:
                code = "ID_INVALID_SSN" if len(re.sub(r"\D", "", s)) == 9 else "ID_INVALID_TIN"
                excs.append(self._make_exc(code, f"Field '{field}': {err}",
                    field=field, value=s))
        return excs

    def _tin_exceptions(self, d, field, require_tin=False):
        return self._tin_exc(d, field, require_tin)

    def _neg(self, d, fields):
        excs = []
        for f in fields:
            v = self._f(d, f)
            if v is not None and v < 0:
                excs.append(self._make_exc("NUM_NEGATIVE_VALUE",
                    f"Field '{f}' is ${v:,.2f}. Negative values not permitted here.",
                    field=f, value=v))
        return excs

    def _negative_check(self, d, fields):
        return self._neg(d, fields)

    def _req(self, d, fields, form):
        excs = []
        for f in fields:
            if d.get(f) is None or str(d.get(f, "")).strip() == "":
                excs.append(self._make_exc("FLD_ZERO_VS_BLANK",
                    f"{form} required field '{f}' is null or missing.",
                    field=f, value=None))
        return excs

    def _required_check(self, d, fields, form):
        return self._req(d, fields, form)

    def _bwcheck(self, d, inc_f, tax_f, form):
        """
        Backup withholding check — 24% per IRC 3406.
        Only fires when the form data or context explicitly signals that
        backup withholding applies (second_tin_notice or backup_withholding_applies).
        Voluntary withholding at other rates is not flagged.
        """
        if not (d.get("second_tin_notice") or d.get("backup_withholding_applies")):
            return []
        excs = []
        inc = self._f(d, inc_f)
        tax = self._f(d, tax_f)
        if inc and tax and tax > 0:
            exp = round(inc * BACKUP_WITHHOLDING_RATE, 2)
            if abs(exp - tax) > max(MATH_TOLERANCE, inc * 0.01):
                excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                    f"{form} backup withholding (${tax:,.2f}) != 24% of {inc_f} "
                    f"(${inc:,.2f}) = ${exp:,.2f}.",
                    field=tax_f, value=tax))
        return excs

    def _backup_withholding_check(self, d, inc_f, tax_f, form):
        return self._bwcheck(d, inc_f, tax_f, form)

    # =========================================================================
    # UNIVERSAL CHECKS
    # =========================================================================

    def _check_universal(self, data, ctx):
        excs = []
        # U1 - FLD_ZERO_VS_BLANK: string zero
        for key, value in data.items():
            if isinstance(value, str) and value.strip() in ("0", "0.0", "0.00"):
                excs.append(self._make_exc("FLD_ZERO_VS_BLANK",
                    f"Field '{key}' contains string zero '{value}' instead of numeric 0 or null. "
                    f"Possible extractor stringification of a missing field.",
                    field=key, value=value))
        # U2 - FLD_SPECIAL_CHARS
        for key, value in data.items():
            if any(key.endswith(s) for s in NUMERIC_FIELD_SUFFIXES):
                if value is not None and isinstance(value, str):
                    noise = re.sub(r'[\d\s\$\,\.\-\(\)\+\/]', '', str(value))
                    if noise:
                        excs.append(self._make_exc("FLD_SPECIAL_CHARS",
                            f"Numeric field '{key}' contains non-numeric characters "
                            f"'{noise}' in value '{value}'. Possible OCR noise.",
                            field=key, value=value))
        # U3 - NUM_DECIMAL_MISPLACE: >10M
        for key in data:
            if any(key.endswith(s) for s in NUMERIC_FIELD_SUFFIXES):
                v = self._f(data, key)
                if v is not None and v > 10_000_000:
                    excs.append(self._make_exc("NUM_DECIMAL_MISPLACE",
                        f"Field '{key}' value ${v:,.2f} exceeds $10,000,000. "
                        f"Verify decimal placement — possible OCR decimal shift.",
                        field=key, value=v))
        # U4 - NUM_LARGE_OUTLIER: 1M-10M
        for key in data:
            if any(key.endswith(s) for s in NUMERIC_FIELD_SUFFIXES):
                v = self._f(data, key)
                if v is not None and 1_000_000 < v <= 10_000_000:
                    excs.append(self._make_exc("NUM_LARGE_OUTLIER",
                        f"Field '{key}' value ${v:,.2f} exceeds $1,000,000. "
                        f"Statistically unusual. Route to Intelligence layer.",
                        field=key, value=v))
        # U5 - LLM_OVER_NORMALIZATION: title-cased name fields
        for field in NAME_FIELDS:
            v = data.get(field)
            if v and isinstance(v, str) and len(v.split()) >= 1:
                if v == v.title() and not v.isupper():
                    excs.append(self._make_exc("LLM_OVER_NORMALIZATION",
                        f"Field '{field}' value '{v}' is title-cased. IRS forms print "
                        f"names in ALL CAPS. LLM may have auto-corrected the spelling.",
                        field=field, value=v))
        # U6 - CY_WRONG_YEAR_UPLOAD
        for field in ["tax_year", "year", "calendar_year", "tax_period"]:
            v = data.get(field)
            if v is not None:
                try:
                    y = int(str(v).strip()[:4])
                    if y < CURRENT_TAX_YEAR - 1:
                        excs.append(self._make_exc("CY_WRONG_YEAR_UPLOAD",
                            f"Field '{field}' year {y} is more than 1 year prior to "
                            f"{CURRENT_TAX_YEAR}. Possible prior-year form uploaded in error.",
                            field=field, value=y))
                    elif y > CURRENT_TAX_YEAR:
                        excs.append(self._make_exc("CY_WRONG_YEAR_UPLOAD",
                            f"Field '{field}' year {y} is in the future (>{CURRENT_TAX_YEAR}).",
                            field=field, value=y))
                except (ValueError, TypeError):
                    pass
        # U7 - NUM_ROUNDING_VARIANCE
        half_cent_fields = [
            k for k in data
            if any(k.endswith(s) for s in NUMERIC_FIELD_SUFFIXES)
            and self._f(data, k) is not None
            and round(abs(self._f(data, k)) * 100) % 10 == 5
        ]
        if half_cent_fields:
            excs.append(self._make_exc("NUM_ROUNDING_VARIANCE",
                f"Fields {half_cent_fields[:3]} contain half-cent values that may "
                f"be affected by IRS rounding rules. Accepted within ${MATH_TOLERANCE:.2f} tolerance.",
                field=half_cent_fields[0], value=None))
        # U8 - FLD_CHECKBOX_BLANK
        CHECKBOX_FIELDS = [
            "schedule_c_attached", "is_final_return", "is_amended",
            "taxpayer_deceased", "spouse_deceased", "is_corrected",
            "second_tin_notice", "fatca_filing_requirement"
        ]
        for field in CHECKBOX_FIELDS:
            if field in data and data[field] is None:
                excs.append(self._make_exc("FLD_CHECKBOX_BLANK",
                    f"Boolean field '{field}' is null. IRS forms interpret unchecked "
                    f"boxes as FALSE. Defaulting to FALSE.",
                    field=field, value=None))
        # U9 - FLD_ADDRESS_COLLAPSED
        for field in ["employee_address", "employer_address", "taxpayer_address",
                      "payer_address", "recipient_address"]:
            v = data.get(field)
            if v and isinstance(v, str):
                has_zip = bool(re.search(r'\d{5}', v))
                has_state = bool(re.search(
                    r'\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|'
                    r'ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|'
                    r'PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b', v))
                has_street = bool(re.search(
                    r'\b\d+\s+\w+\s+(St|Ave|Blvd|Dr|Rd|Ln|Ct|Way|Pl)\b', v, re.IGNORECASE))
                no_newline = '\n' not in v and len(v) > 40
                if has_zip and has_state and has_street and no_newline:
                    excs.append(self._make_exc("FLD_ADDRESS_COLLAPSED",
                        f"Field '{field}' appears to have a multi-line address collapsed "
                        f"into a single line: '{v[:60]}...'. Structured re-parse needed.",
                        field=field, value=v))
        # U10 - FLD_NA_TEXT and FLD_DASH_SYMBOL
        for key, value in data.items():
            if value is not None and isinstance(value, str):
                s = value.strip().upper()
                if s in ("N/A", "NA", "N.A.", "NONE"):
                    excs.append(self._make_exc("FLD_NA_TEXT",
                        f"Field '{key}' contains N/A text '{value}'. Converted to structured null.",
                        field=key, value=value))
                elif value.strip() in ("\u2014", "\u2013", "-", "--"):
                    excs.append(self._make_exc("FLD_DASH_SYMBOL",
                        f"Field '{key}' uses dash symbol '{value}' instead of zero. Normalized to 0.0.",
                        field=key, value=value))
        
        excs.extend(self._field_exceptions)
        self._field_exceptions = []
        return excs

    # =========================================================================
    # CONTEXT CHECKS
    # =========================================================================

    def _check_ocr(self, ctx):
        excs = []
        ocr = (ctx or {}).get("ocr", {})
        if not ocr:
            return excs
        if ocr.get("is_cropped"):
            excs.append(self._make_exc("OCR_CROPPED",
                "Document appears cropped — form edges are missing. "
                "Block extraction and request re-scan.", field=None, value=None))
        if ocr.get("is_rotated"):
            excs.append(self._make_exc("OCR_ROTATED",
                "Document scan is rotated. Auto-rotate before extraction.",
                field=None, value=None))
        if ocr.get("is_corrupted"):
            excs.append(self._make_exc("OCR_CORRUPTED_PDF",
                "PDF is corrupted or unreadable. Reject and request re-upload.",
                field=None, value=None))
        if ocr.get("multi_form_detected"):
            excs.append(self._make_exc("OCR_MULTI_FORM_PDF",
                "Multiple IRS forms detected in a single PDF upload. "
                "Segment pages before extraction.", field=None, value=None))
        conf = ocr.get("confidence")
        if conf is not None and conf < OCR_CONFIDENCE_THRESHOLD:
            excs.append(self._make_exc("OCR_LOW_CONFIDENCE",
                f"Overall OCR confidence {conf:.0%} is below the "
                f"{OCR_CONFIDENCE_THRESHOLD:.0%} threshold. "
                f"Re-run extraction or route to manual review.",
                field=None, value=conf))
        field_conf = ocr.get("field_confidence", {})
        for field, fc in field_conf.items():
            if fc is not None and fc < FIELD_CONFIDENCE_THRESHOLD:
                excs.append(self._make_exc("FLD_ILLEGIBLE",
                    f"Field '{field}' OCR confidence {fc:.0%} is below "
                    f"{FIELD_CONFIDENCE_THRESHOLD:.0%}. Re-run or manual review.",
                    field=field, value=fc))
        hashes = ocr.get("page_hashes", [])
        if len(hashes) != len(set(hashes)):
            dupes = [h for h in hashes if hashes.count(h) > 1]
            excs.append(self._make_exc("OCR_DUPLICATE_PAGE",
                f"Duplicate page detected (hash repeated: {dupes[0][:16]}...). "
                f"Remove duplicate before extraction.",
                field=None, value=dupes[0]))
        return excs

    def _check_email(self, ctx):
        excs = []
        email = (ctx or {}).get("email", {})
        if not email:
            return excs
        if email.get("sender_registered") is False:
            domain = email.get("sender_domain", "unknown")
            excs.append(self._make_exc("EMAIL_UNKNOWN_SENDER",
                f"Form received from unregistered sender domain '{domain}'. "
                f"Validate by cross-referencing SSN against client records.",
                field=None, value=domain))
        if email.get("is_cpa_forward"):
            excs.append(self._make_exc("EMAIL_CPA_FORWARD",
                "Email was forwarded by a CPA on behalf of their client. "
                "Match SSN to CPA client list before processing.",
                field=None, value=None))
        risk = email.get("spoofing_risk_score", 0)
        if risk >= SPOOFING_RISK_THRESHOLD:
            domain = email.get("sender_domain", "unknown")
            excs.append(self._make_exc("EMAIL_SPOOFED",
                f"Sender domain '{domain}' has spoofing risk score {risk:.0%} "
                f"(threshold {SPOOFING_RISK_THRESHOLD:.0%}). "
                f"Apply risk scoring and trigger security alert.",
                field=None, value=risk))
        ssns = email.get("client_ssns_found", [])
        if len(ssns) > 1:
            excs.append(self._make_exc("EMAIL_MULTI_CLIENT",
                f"Email contains {len(ssns)} client SSNs across attachments. "
                f"Split attachments and match each to respective client.",
                field=None, value=len(ssns)))
        if email.get("has_metadata") is False:
            excs.append(self._make_exc("EMAIL_NO_METADATA",
                "Attachment has no client identifier metadata. "
                "Extract then resolve client identity by SSN lookup.",
                field=None, value=None))
        if email.get("is_encrypted"):
            excs.append(self._make_exc("EMAIL_ENCRYPTED_PDF",
                "PDF attachment is password-protected. "
                "Trigger password workflow before extraction.",
                field=None, value=None))
        return excs

    def _check_engagement(self, ctx, form_type, data):
        excs = []
        eng = (ctx or {}).get("engagement", {})
        if not eng:
            return excs
        if eng.get("client_found") is False:
            excs.append(self._make_exc("ENG_UNKNOWN_CLIENT",
                f"Form '{form_type}' received but client not found in engagement system. "
                f"Route to Unmatched Queue for manual assignment.",
                field=None, value=None))
            return excs
        if eng.get("client_deleted"):
            excs.append(self._make_exc("ENG_CLIENT_DELETED",
                "Client record has been deleted but documents are still arriving. "
                "Reject document and notify administrator.",
                field=None, value=None))
        if eng.get("duplicate_profile_detected"):
            excs.append(self._make_exc("ENG_DUPLICATE_PROFILE",
                "Same SSN detected in two separate client profiles. "
                "Escalate to identity resolution before processing.",
                field=None, value=None))
        if eng.get("client_active") is False:
            excs.append(self._make_exc("ENG_INACTIVE",
                f"Client engagement for tax year {eng.get('engagement_year', CURRENT_TAX_YEAR)} "
                f"has not been opened. Mark as pre-engagement.",
                field=None, value=eng.get("engagement_year")))
        form_year = eng.get("form_tax_year")
        eng_year = eng.get("engagement_year")
        if form_year and eng_year and form_year != eng_year:
            excs.append(self._make_exc("ENG_WRONG_YEAR",
                f"Form tax year {form_year} does not match open engagement year {eng_year}. "
                f"Route to correct workflow year.",
                field="tax_year", value=form_year))
        entity_type = eng.get("client_entity_type", "")
        BUSINESS_FORMS = {"1065", "1120", "1120-S", "K-1-1065", "K-1-1120S"}
        INDIVIDUAL_FORMS = {"1040", "W-2", "1099-NEC", "1099-INT", "1099-DIV",
                            "1099-R", "1099-MISC", "1099-B", "1099-G", "1099-K"}
        if entity_type == "individual" and form_type in BUSINESS_FORMS:
            excs.append(self._make_exc("ENG_WRONG_ENTITY",
                f"Business form '{form_type}' received under individual client engagement. "
                f"Block and flag for entity-type correction.",
                field=None, value=form_type))
        elif entity_type == "business" and form_type in INDIVIDUAL_FORMS:
            excs.append(self._make_exc("ENG_WRONG_ENTITY",
                f"Individual form '{form_type}' received under business entity engagement. "
                f"Verify correct entity.", field=None, value=form_type))
        if eng.get("client_merged"):
            alias = eng.get("merged_alias", "unknown")
            excs.append(self._make_exc("ENG_CLIENT_MERGED",
                f"Client has been merged or renamed. Prior alias: '{alias}'. "
                f"Maintain alias mapping to prevent data loss.",
                field=None, value=alias))
        # C10 — ID_NAME_TIN_MISMATCH: cross-reference employer/payer name against known TIN map
        known_tin_names = eng.get("known_tin_name_map", {})
        employer_tin  = data.get("employer_tin") or data.get("payer_tin")
        employer_name = data.get("employer_name") or data.get("payer_name")
        if employer_tin and employer_name and employer_tin in known_tin_names:
            canonical = known_tin_names[employer_tin]
            def _norm(s):
                return re.sub(r'[^a-z0-9 ]', '', s.lower()).strip()
            if _norm(canonical) not in _norm(employer_name) and \
               _norm(employer_name) not in _norm(canonical):
                excs.append(self._make_exc("ID_NAME_TIN_MISMATCH",
                    f"Employer name '{employer_name}' does not match the registered "
                    f"name '{canonical}' for TIN '{employer_tin}'. "
                    f"Possible misrouted or fraudulent document.",
                    field="employer_tin", value=employer_tin))
        return excs

    def _check_tenant(self, ctx):
        excs = []
        tenant = (ctx or {}).get("tenant", {})
        if not tenant:
            return excs
        current = tenant.get("current_tenant_id")
        ssn_map = tenant.get("ssn_tenant_map", {})
        for ssn, owner_tenant in ssn_map.items():
            if owner_tenant != current:
                excs.append(self._make_exc("MT_CROSS_TENANT_CLIENT",
                    f"SSN belongs to a client in tenant '{owner_tenant}', "
                    f"not current tenant '{current}'. Hard isolation block.",
                    field=None, value=owner_tenant))
                break
        target = tenant.get("target_s3_bucket")
        actual = tenant.get("detected_s3_bucket")
        if target and actual and target != actual:
            excs.append(self._make_exc("MT_CROSS_TENANT_DOC",
                f"Document routed to S3 bucket '{actual}' but should go to '{target}'. "
                f"Security block — cross-tenant document routing detected.",
                field=None, value=actual))
        if tenant.get("shared_family_account"):
            excs.append(self._make_exc("MT_SHARED_FAMILY",
                "Joint return detected with separate client logins. "
                "Apply household linking model.", field=None, value=None))
        return excs

    def _check_workflow(self, ctx, form_type):
        excs = []
        wf = (ctx or {}).get("workflow", {})
        if not wf:
            return excs
        # C11 — LED_CLIENT_WAIVED: form explicitly confirmed-waived by client
        waived_forms = wf.get("client_waived_forms", [])
        if form_type in waived_forms:
            excs.append(self._make_exc("LED_CLIENT_WAIVED",
                f"Form '{form_type}' is in the client's confirmed-waived list. "
                f"Client has stated they have no {form_type} this tax year. "
                f"Mark as waived and suppress partial-form-set blocking for this type.",
                field=None, value=form_type))
        status = wf.get("ledger_status")
        if status == "closed":
            excs.append(self._make_exc("WF_AFTER_CLOSED",
                f"Document '{form_type}' received after ledger was closed. "
                f"Reopen engagement or hold for next cycle.",
                field=None, value=None))
        if wf.get("is_reupload") and wf.get("prior_version_exists"):
            excs.append(self._make_exc("WF_REUPLOAD",
                f"Re-upload of '{form_type}' detected (prior version exists). "
                f"Increment document version and re-extract.",
                field=None, value=None))
        if wf.get("ledger_updated") is False:
            excs.append(self._make_exc("WF_LEDGER_NOT_UPDATED",
                "Extraction completed but ledger was not updated. "
                "Orchestrator repair required — state inconsistency detected.",
                field=None, value=None))
        if wf.get("manual_override") and not wf.get("audit_trail_present"):
            excs.append(self._make_exc("WF_MANUAL_NO_AUDIT",
                "Manual override applied without a corresponding audit trail entry. "
                "Block until override is logged.", field=None, value=None))
        forms_in_ledger = wf.get("forms_in_ledger", [])
        if forms_in_ledger and form_type not in forms_in_ledger:
            excs.append(self._make_exc("LED_FORM_NOT_IN_LEDGER",
                f"Form '{form_type}' received but not listed in client ledger. "
                f"Add dynamic ledger entry.", field=None, value=form_type))
        instance_count = wf.get("form_instance_count", {})
        if instance_count.get(form_type, 0) > 1:
            excs.append(self._make_exc("LED_MULTIPLE_SAME_FORM",
                f"Multiple instances of '{form_type}' detected "
                f"({instance_count[form_type]} total). Multi-instance support required.",
                field=None, value=instance_count[form_type]))
        return excs

    def _check_session(self, ctx, form_type, data):
        excs = []
        sess = (ctx or {}).get("session", {})
        if not sess:
            return excs
        doc_hash = data.get("_document_hash")
        processed = sess.get("processed_hashes", [])
        if doc_hash and doc_hash in processed:
            excs.append(self._make_exc("XDOC_DUPLICATE_UPLOAD",
                f"Document hash '{doc_hash[:16]}...' already processed this session. "
                f"Ignore duplicate upload.", field=None, value=doc_hash))
        recipient_ssn = data.get("recipient_tin") or data.get("employee_ssn")
        dep_ssns = sess.get("dependent_ssns", [])
        if recipient_ssn and recipient_ssn in dep_ssns:
            excs.append(self._make_exc("ID_DUPLICATE_DEP_SSN",
                f"The SSN on this '{form_type}' matches a known dependent SSN. "
                f"Reject — same SSN cannot be used for both taxpayer and dependent.",
                field="recipient_tin", value=recipient_ssn))
        state_income = sess.get("state_income_reported")
        federal_income = sess.get("federal_income_reported")
        if state_income and federal_income:
            diff = abs(state_income - federal_income)
            if diff > STATE_FEDERAL_INCOME_CONFLICT_THRESHOLD:
                excs.append(self._make_exc("XDOC_CONFLICT_INCOME",
                    f"State income reported (${state_income:,.2f}) differs from "
                    f"federal income (${federal_income:,.2f}) by ${diff:,.2f}. "
                    f"Flag for CPA review.", field=None, value=diff))
        py_forms = sess.get("prior_year_forms", [])
        cy_forms = sess.get("current_year_forms", [])
        if py_forms and cy_forms:
            missing = [f for f in py_forms if f not in cy_forms and f != form_type]
            for mf in missing:
                excs.append(self._make_exc("XDOC_MISSING_RECURRING",
                    f"Form '{mf}' was present in prior year but is absent this year. "
                    f"Intelligence alert — verify if expected.",
                    field=None, value=mf))
        if state_income and not federal_income:
            excs.append(self._make_exc("XDOC_STATE_MISMATCH",
                f"State income (${state_income:,.2f}) reported but no federal income "
                f"base found. Cross-form validation required.",
                field=None, value=state_income))
        state_tax = self._f(data, "state_income_tax_withheld")
        if state_tax and not federal_income:
            excs.append(self._make_exc("CTX_STATE_NO_FED",
                f"State tax withheld (${state_tax:,.2f}) but no federal income base found. "
                f"Cross-form validation required.",
                field="state_income_tax_withheld", value=state_tax))
        py_cap_loss = sess.get("prior_year_cap_loss", 0)
        if py_cap_loss and py_cap_loss > 0:
            cap_loss_cy = self._f(data, "capital_loss_carryover")
            if cap_loss_cy is None:
                excs.append(self._make_exc("CTX_CAP_LOSS_MISSING",
                    f"Prior year capital loss carryover of ${py_cap_loss:,.2f} expected "
                    f"but not found on this year's return. Cross-year validation required.",
                    field="capital_loss_carryover", value=py_cap_loss))
        if sess.get("prior_year_estimated_payments", 0) > 0:
            est_payments = self._f(data, "estimated_tax_payments")
            if est_payments is None:
                py_est = sess.get("prior_year_estimated_payments")
                excs.append(self._make_exc("CY_CARRYOVER_MISSING",
                    f"Prior year showed estimated tax payments (${py_est:,.2f}) "
                    f"but estimated_tax_payments is absent this year.",
                    field="estimated_tax_payments", value=py_est))
        est = self._f(data, "estimated_tax_payments")
        if est and est > 0 and "1040" not in (sess.get("current_year_forms") or []):
            excs.append(self._make_exc("CY_EST_NOT_FILED",
                f"Estimated tax payments (${est:,.2f}) are present but no 1040 "
                f"has been filed this year. CPA review trigger.",
                field="estimated_tax_payments", value=est))
        if form_type.startswith("1099"):
            form_ssn = data.get("recipient_tin")
            if form_ssn and form_ssn in dep_ssns:
                excs.append(self._make_exc("CTX_DEP_FORM",
                    f"1099 form received under a dependent's SSN. "
                    f"Link to dependent entity record.",
                    field="recipient_tin", value=form_ssn))
        tin = data.get("employer_tin") or data.get("payer_tin")
        known_tins = sess.get("known_tins", [])
        if tin and known_tins and tin not in known_tins:
            excs.append(self._make_exc("ID_NEW_EMPLOYER_TIN",
                f"TIN '{tin}' has not been seen before in this engagement. "
                f"Allow processing but flag for review.",
                field="employer_tin", value=tin))
        expected = (ctx or {}).get("workflow", {}).get("forms_in_ledger", [])
        cy_forms_set = set(sess.get("current_year_forms", []))
        if expected:
            waived_forms = (ctx or {}).get("workflow", {}).get("client_waived_forms", [])
            missing_required = [f for f in expected
                                if f not in cy_forms_set and f not in waived_forms]
            if missing_required:
                excs.append(self._make_exc("LED_PARTIAL_FORM_SET",
                    f"Required forms {missing_required} are listed in ledger "
                    f"but have not been received. Block until full set is uploaded.",
                    field=None, value=missing_required))
        return excs

    def _check_security(self, ctx):
        excs = []
        sec = (ctx or {}).get("security", {})
        if not sec:
            return excs
        if sec.get("pii_in_logs_detected"):
            excs.append(self._make_exc("SEC_PII_IN_LOGS",
                "PII detected in application logs. Mask immediately and alert security team.",
                field=None, value=None))
        if sec.get("unauthorized_role"):
            excs.append(self._make_exc("SEC_UNAUTHORIZED_ACCESS",
                "Access attempted by unauthorized role. Hard fail and write audit entry.",
                field=None, value=None))
        if sec.get("s3_public_access"):
            excs.append(self._make_exc("SEC_S3_PUBLIC",
                "S3 bucket has public access configured. Trigger security alert immediately.",
                field=None, value=None))
        expected_hash = sec.get("document_hash_expected")
        actual_hash = sec.get("document_hash_actual")
        if expected_hash and actual_hash and expected_hash != actual_hash:
            excs.append(self._make_exc("SEC_TAMPERED_DOC",
                f"Document hash mismatch. Expected '{expected_hash[:16]}...' "
                f"but got '{actual_hash[:16]}...'. Lock document and investigate.",
                field=None, value=actual_hash))
        attempts = sec.get("extraction_attempt_count", 0)
        if attempts > EXTRACTION_ATTEMPT_LIMIT:
            excs.append(self._make_exc("SEC_EXCESS_ATTEMPTS",
                f"{attempts} extraction attempts detected in rate-limit window. "
                f"Rate-limit and alert security team.",
                field=None, value=attempts))
        return excs

    def _check_llm_pipeline(self, ctx, data):
        excs = []
        llm = (ctx or {}).get("llm", {})
        if not llm:
            return excs
        ctx_client = llm.get("context_client_id")
        ext_client = llm.get("extracted_client_id")
        if ctx_client and ext_client and ctx_client != ext_client:
            excs.append(self._make_exc("LLMD_CROSS_CLIENT_BLEED",
                f"LLM context was loaded for client '{ctx_client}' but extracted "
                f"data belongs to client '{ext_client}'. Stateless extraction required.",
                field=None, value=ext_client))
        tokens = llm.get("context_window_tokens", 0)
        if tokens > CONTEXT_WINDOW_TOKEN_LIMIT:
            excs.append(self._make_exc("LLMD_CONTEXT_OVERFLOW",
                f"LLM context window is {tokens:,} tokens (limit {CONTEXT_WINDOW_TOKEN_LIMIT:,}). "
                f"Use page-isolated prompts to prevent cross-page extraction errors.",
                field=None, value=tokens))
        ext_page = llm.get("extraction_page")
        exp_page = llm.get("expected_page")
        if ext_page is not None and exp_page is not None and ext_page != exp_page:
            excs.append(self._make_exc("LLM_CROSS_PAGE_BLEED",
                f"Value extracted from page {ext_page} but expected from page {exp_page}. "
                f"Use page-isolated prompts.", field=None, value=ext_page))
        boxes = llm.get("field_bounding_boxes", {})
        for field, bbox in boxes.items():
            expected_box = bbox.get("expected")
            actual_box = bbox.get("actual")
            if expected_box and actual_box:
                x_drift = abs(expected_box[0] - actual_box[0])
                y_drift = abs(expected_box[1] - actual_box[1])
                if BBOX_COORD_SPACE == "normalised":
                    drift_threshold = 0.20
                else:
                    drift_threshold = BBOX_PIXEL_DRIFT_THRESHOLD
                if x_drift > drift_threshold or y_drift > drift_threshold:
                    excs.append(self._make_exc("LLM_CONTEXT_DRIFT",
                        f"Field '{field}' extracted from unexpected location. "
                        f"Bounding box drift: x={x_drift:.0%}, y={y_drift:.0%}.",
                        field=field, value=actual_box))
        page_assign = llm.get("multi_form_page_assignment", {})
        if len(set(page_assign.values())) > 1:
            excs.append(self._make_exc("LLMD_MULTI_FORM_MISASSIGN",
                f"Multi-form PDF has pages assigned to: {list(set(page_assign.values()))}. "
                f"Verify page-to-form segmentation before extraction.",
                field=None, value=page_assign))
        for key, value in data.items():
            if any(key.endswith(s) for s in NUMERIC_FIELD_SUFFIXES):
                if isinstance(value, str):
                    words = re.findall(
                        r'\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|'
                        r'hundred|thousand|million|billion)\b', value.lower())
                    if words:
                        excs.append(self._make_exc("LLM_NUMERIC_WORD_ERR",
                            f"Field '{key}' contains textual number words {words} "
                            f"in value '{value}'. Strict numeric extraction required.",
                            field=key, value=value))
        if llm.get("hallucinated_fields"):
            for field in llm["hallucinated_fields"]:
                excs.append(self._make_exc("LLM_HALLUCINATED",
                    f"Field '{field}' value flagged as hallucinated by OCR anchor check. "
                    f"Value not present in original document.",
                    field=field, value=data.get(field)))
        if llm.get("blank_as_missing_fields"):
            for field in llm["blank_as_missing_fields"]:
                excs.append(self._make_exc("LLM_BLANK_AS_MISSING",
                    f"Field '{field}' is intentionally blank on the form but was flagged "
                    f"as missing by the extractor. Enforce schema null rules.",
                    field=field, value=None))
        if llm.get("reordered_fields"):
            excs.append(self._make_exc("LLM_REORDERED_MAP",
                f"Fields {llm['reordered_fields']} appear to be misaligned to wrong boxes. "
                f"Apply template coordinate validation.",
                field=None, value=llm["reordered_fields"]))
        if llm.get("over_inferred_fields"):
            for field in llm["over_inferred_fields"]:
                excs.append(self._make_exc("LLM_OVER_INFERENCE",
                    f"Field '{field}' was inferred/filled by LLM rather than extracted "
                    f"directly. Disable inference mode for this field.",
                    field=field, value=data.get(field)))
        return excs

    def _check_db_schema(self, ctx, data):
        excs = []
        db = (ctx or {}).get("db", {})
        if db.get("json_flatten_failed"):
            excs.append(self._make_exc("DB_JSON_FLATTEN_FAIL",
                "JSON schema flattening failed. Rollback transaction.",
                field=None, value=None))
        null_violations = db.get("null_non_nullable_fields", [])
        for field in null_violations:
            excs.append(self._make_exc("DB_NULL_NON_NULLABLE",
                f"Field '{field}' is null but maps to a non-nullable DB column. Block insert.",
                field=field, value=None))
        if db.get("duplicate_pk"):
            excs.append(self._make_exc("DB_DUPLICATE_PK",
                "Primary key already exists in database. Enforce idempotent processing.",
                field=None, value=db.get("pk_value")))
        if db.get("schema_drift_detected"):
            excs.append(self._make_exc("DB_SCHEMA_DRIFT",
                "Extracted form structure differs from registered schema version. "
                "Trigger schema review workflow.",
                field=None, value=db.get("schema_version")))
        for key, value in data.items():
            if any(key.endswith(s) for s in NUMERIC_FIELD_SUFFIXES):
                if value is not None and not isinstance(value, (int, float)):
                    if self._f(data, key) is None and str(value).strip() not in ("", "N/A"):
                        excs.append(self._make_exc("DB_TYPE_CONFLICT",
                            f"Field '{key}' expected numeric type but contains "
                            f"unparseable value '{value}'. Coerce or reject.",
                            field=key, value=value))
        return excs

    def _check_structural(self, data, ctx):
        excs = []
        schema = (ctx or {}).get("schema", {})
        if schema.get("missing_pages"):
            if schema.get("variant_validated"):
                for page in schema["missing_pages"]:
                    excs.append(self._make_exc("STR_MULTI_PAGE_VARIANT",
                        f"Page '{page}' is missing but validated as not required for this variant.",
                        field=None, value=page))
            else:
                excs.append(self._make_exc("OCR_CROPPED",
                    f"Pages {schema['missing_pages']} are absent and no variant schema "
                    f"has confirmed them as optional. Possible cropped or incomplete upload.",
                    field=None, value=schema["missing_pages"]))
        if schema.get("layout_year") and schema.get("layout_year") != CURRENT_TAX_YEAR:
            excs.append(self._make_exc("STR_ALT_LAYOUT",
                f"Form uses IRS layout year {schema['layout_year']} which differs from "
                f"current {CURRENT_TAX_YEAR} template. Apply version-aware extraction.",
                field=None, value=schema["layout_year"]))
        for field in (schema.get("conditional_skipped_fields") or []):
            excs.append(self._make_exc("STR_CONDITIONAL_SKIP",
                f"Field '{field}' was skipped because its parent condition was not met.",
                field=field, value=None))
        for field in (schema.get("deprecated_fields_present") or []):
            excs.append(self._make_exc("STR_DEPRECATED_FIELD",
                f"Field '{field}' is deprecated for tax year {CURRENT_TAX_YEAR} "
                f"but was found in extracted data.",
                field=field, value=data.get(field)))
        for field in (schema.get("intentionally_blank_fields") or []):
            excs.append(self._make_exc("STR_OPTIONAL_BLANK",
                f"Field '{field}' is intentionally blank (NULL_ALLOWED per schema).",
                field=field, value=None))
        return excs

    # =========================================================================
    # MAIN validate() METHOD
    # =========================================================================

    def validate(self, form_type: str, data: dict, context: dict = None, human_verified_fields: list[str] | None = None) -> dict:
        self._field_exceptions = []
        if not data or not isinstance(data, dict):
            exc = self._make_exc("FLD_ZERO_VS_BLANK",
                "No data extracted. Pipeline returned empty or null.",
                field=None, value=None)
            return self._build_result("LOW", [exc], data or {}, [exc])
        ctx = context or {}
        self._ctx = ctx
        universal   = self._check_universal(data, ctx)
        method_name = "_validate_" + form_type.replace("-","_").replace(" ","_")\
                                               .replace("(","").replace(")","")
        validator = getattr(self, method_name, self._validate_unknown)
        try:
            form_excs = validator(data)
        except Exception as e:
            form_excs = [self._make_exc("DB_TYPE_CONFLICT",
                f"Validator internal error for {form_type}: {str(e)}", field=None)]
        ocr_excs    = self._check_ocr(ctx)
        email_excs  = self._check_email(ctx)
        eng_excs    = self._check_engagement(ctx, form_type, data)
        tenant_excs = self._check_tenant(ctx)
        wf_excs     = self._check_workflow(ctx, form_type)
        sess_excs   = self._check_session(ctx, form_type, data)
        sec_excs    = self._check_security(ctx)
        llm_excs    = self._check_llm_pipeline(ctx, data)
        db_excs     = self._check_db_schema(ctx, data)
        struct_excs = self._check_structural(data, ctx)
        all_excs = (universal + form_excs + ocr_excs + email_excs +
                    eng_excs + tenant_excs + wf_excs + sess_excs +
                    sec_excs + llm_excs + db_excs + struct_excs)

        # Filter out exceptions for fields that have been human-verified
        if human_verified_fields:
            hv_set = set(human_verified_fields)
            all_excs = [e for e in all_excs if e.get("field") not in hv_set]
        sevs = {e["severity"] for e in all_excs}
        if "CRITICAL" in sevs or "BLOCKING" in sevs:
            confidence = "LOW"
        elif "WARNING" in sevs:
            confidence = "MEDIUM"
        else:
            confidence = "HIGH"
        return self._build_result(confidence, all_excs, data, all_excs)

    def _build_result(self, confidence, all_excs, data, exceptions):
        errors = [e["description"] for e in all_excs
                  if e["severity"] in ("BLOCKING","CRITICAL","WARNING")]
        summary = {
            "total":    len(all_excs),
            "critical": sum(1 for e in all_excs if e["severity"] == "CRITICAL"),
            "blocking": sum(1 for e in all_excs if e["severity"] == "BLOCKING"),
            "warning":  sum(1 for e in all_excs if e["severity"] == "WARNING"),
            "info":     sum(1 for e in all_excs if e["severity"] == "INFO"),
            # legacy lowercase keys for backward compat
            "CRITICAL": sum(1 for e in all_excs if e["severity"] == "CRITICAL"),
            "BLOCKING": sum(1 for e in all_excs if e["severity"] == "BLOCKING"),
            "WARNING":  sum(1 for e in all_excs if e["severity"] == "WARNING"),
            "INFO":     sum(1 for e in all_excs if e["severity"] == "INFO"),
        }
        return {"confidence": confidence, "errors": errors,
                "data": data, "exceptions": exceptions, "summary": summary}

    def _validate_unknown(self, data):
        null_count = sum(1 for v in data.values() if v is None)
        total = len(data)
        if total == 0 or null_count == total:
            return [self._make_exc("FLD_ZERO_VS_BLANK",
                "All fields null. Extraction failed.", field=None)]
        if total > 0 and null_count / total > NULL_RATIO_WARNING_THRESHOLD:
            return [self._make_exc("STR_OPTIONAL_BLANK",
                f"{null_count}/{total} fields null (>70%). Review extraction.",
                value=null_count)]
        return []

    def _validate_generic_1099(self, d, form_name):
        try:
            excs = []
            payer_field = next(
                (f for f in ["payer_tin", "payer_tin"] if d.get(f) is not None), None)
            if payer_field:
                excs += self._tin_exc(d, payer_field, require_tin=True)
            else:
                excs.append(self._make_exc("FLD_ZERO_VS_BLANK",
                    f"{form_name} payer TIN (payer_tin or payer_tin) is missing.",
                    field="payer_tin"))
            excs += self._tin_exc(d, "recipient_tin", require_tin=False)
            numeric_vals = [self._f(d, k) for k in d
                            if any(k.endswith(s) for s in NUMERIC_FIELD_SUFFIXES)]
            if not any(v is not None and v > 0 for v in numeric_vals):
                excs.append(self._make_exc("FLD_ZERO_VS_BLANK",
                    f"{form_name} has no positive income values extracted.",
                    field=None))
            bw_field = next((f for f in ["federal_income_tax_withheld","federal_tax_withheld"]
                             if self._f(d, f) is not None and (self._f(d, f) or 0) > 0), None)
            income_field = next((k for k in d
                                 if any(k.endswith(s) for s in NUMERIC_FIELD_SUFFIXES)
                                 and k not in ["payer_tin","payer_tin","recipient_tin"]
                                 and self._f(d, k) is not None
                                 and (self._f(d, k) or 0) > 0), None)
            if bw_field and income_field:
                excs += self._bwcheck(d, income_field, bw_field, form_name)
            return excs
        except Exception as e:
            return [self._make_exc("DB_TYPE_CONFLICT",
                f"Validator internal error for {form_name}: {str(e)}", field=None)]

    def _validate_1099_Q(self, d):    return self._validate_generic_1099(d, "1099-Q")
    def _validate_1099_SA(self, d):   return self._validate_generic_1099(d, "1099-SA")
    def _validate_1099_OID(self, d):  return self._validate_generic_1099(d, "1099-OID")
    def _validate_1099_PATR(self, d): return self._validate_generic_1099(d, "1099-PATR")
    def _validate_1099_LS(self, d):   return self._validate_generic_1099(d, "1099-LS")
    def _validate_1099_LTC(self, d):  return self._validate_generic_1099(d, "1099-LTC")

    # =========================================================================
    # FORM VALIDATORS
    # =========================================================================

    def _validate_W_2(self, d):
        try:
            excs = []
            excs += self._req(d, ["wages_tips_compensation","employee_ssn",
                                   "employer_tin","employer_name","employee_name"], "W-2")
            excs += self._neg(d, ["wages_tips_compensation","federal_income_tax_withheld",
                                   "social_security_wages","social_security_tax_withheld",
                                   "medicare_wages_and_tips","medicare_tax_withheld"])
            ss_wages = self._f(d, "social_security_wages")
            ss_tax   = self._f(d, "social_security_tax_withheld")
            if ss_wages is not None and ss_tax is not None:
                expected = round(ss_wages * SS_RATE, 2)
                diff = abs(expected - ss_tax)
                if diff > MATH_TOLERANCE:
                    excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                        f"W-2 Box 4 SS tax withheld (${ss_tax:,.2f}) does not equal "
                        f"Box 3 SS wages (${ss_wages:,.2f}) x 6.2% = ${expected:,.2f}. "
                        f"Difference: ${diff:,.2f}.",
                        field="social_security_tax_withheld", value=ss_tax))
            med_wages = self._f(d, "medicare_wages_and_tips")
            med_tax   = self._f(d, "medicare_tax_withheld")
            if med_wages is not None and med_tax is not None:
                expected = round(med_wages * MEDICARE_RATE, 2)
                diff = abs(expected - med_tax)
                if diff > MATH_TOLERANCE:
                    excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                        f"W-2 Box 6 Medicare tax (${med_tax:,.2f}) does not equal "
                        f"Box 5 Medicare wages (${med_wages:,.2f}) x 1.45% = ${expected:,.2f}.",
                        field="medicare_tax_withheld", value=med_tax))
            wages = self._f(d, "wages_tips_compensation")
            if wages is not None and med_wages is not None and wages > 0:
                if med_wages < wages - MATH_TOLERANCE:
                    excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                        f"W-2 Box 5 Medicare wages (${med_wages:,.2f}) < Box 1 wages "
                        f"(${wages:,.2f}). Medicare has no wage base cap.",
                        field="medicare_wages_and_tips", value=med_wages))
            if ss_wages is not None and ss_wages > SS_WAGE_BASE + MATH_TOLERANCE:
                excs.append(self._make_exc("NUM_LARGE_OUTLIER",
                    f"W-2 Box 3 SS wages (${ss_wages:,.2f}) exceeds 2026 SS wage base "
                    f"${SS_WAGE_BASE:,.2f}.",
                    field="social_security_wages", value=ss_wages))
            if ss_tax is not None and ss_tax > MAX_SS_TAX + MATH_TOLERANCE:
                excs.append(self._make_exc("NUM_LARGE_OUTLIER",
                    f"W-2 Box 4 SS tax (${ss_tax:,.2f}) exceeds 2026 maximum ${MAX_SS_TAX:,.2f}.",
                    field="social_security_tax_withheld", value=ss_tax))
            dep_care = self._f(d, "dependent_care_benefits")
            if dep_care is not None and dep_care > DEP_CARE_LIMIT + MATH_TOLERANCE:
                excs.append(self._make_exc("CTX_FILING_STATUS_DEP",
                    f"W-2 Box 10 dependent care (${dep_care:,.2f}) exceeds 2026 limit "
                    f"${DEP_CARE_LIMIT:,.2f}.",
                    field="dependent_care_benefits", value=dep_care))
            ssn = d.get("employee_ssn")
            if ssn is not None:
                err, is_masked = self._check_tin(str(ssn))
                if is_masked:
                    excs.append(self._make_exc("ID_MASKED_SSN",
                        f"W-2 employee_ssn appears masked/redacted.",
                        field="employee_ssn", value=str(ssn)))
                elif err:
                    excs.append(self._make_exc("ID_INVALID_SSN",
                        f"W-2 employee_ssn: {err}",
                        field="employee_ssn", value=str(ssn)))
            excs += self._tin_exc(d, "employer_tin", require_tin=True)
            return excs
        except Exception as e:
            return [self._make_exc("DB_TYPE_CONFLICT",
                f"Validator internal error for W-2: {str(e)}", field=None)]

    def _is_image_only_1040_context(self, ctx):
        """
        Keep 1040 image-only behavior aligned with 1040_exception_report.md.
        """
        c = ctx or {}
        ocr = c.get("ocr", {}) if isinstance(c.get("ocr", {}), dict) else {}
        doc = c.get("document", {}) if isinstance(c.get("document", {}), dict) else {}
        pdf_type = str(c.get("pdf_type", "")).strip().lower()
        return any([
            pdf_type == "scanned",
            bool(ocr.get("image_only")),
            bool(ocr.get("is_scanned")),
            bool(ocr.get("no_text_layer")),
            doc.get("has_text_layer") is False,
        ])

    def _validate_1040_scan_profile(self, d, ctx):
        """
        1040 scan-first profile:
        image/no-text uploads should surface OCR/manual-review exceptions early.
        """
        if not self._is_image_only_1040_context(ctx):
            return []

        excs = []
        seen = set()

        def add_once(code, description, field=None, value=None):
            key = (code, field)
            if key in seen:
                return
            seen.add(key)
            excs.append(self._make_exc(code, description, field=field, value=value))

        add_once(
            "OCR_LOW_CONFIDENCE",
            "1040 appears image-only (no text layer). Route through OCR pipeline before strict field/arithmetic validation.",
            field=None,
            value=0.0,
        )

        critical_fields = ["taxpayer_ssn", "total_income", "adjusted_gross_income"]
        for f in critical_fields:
            v = d.get(f)
            if v is None or str(v).strip() == "":
                add_once(
                    "FLD_ZERO_VS_BLANK",
                    f"1040 required field '{f}' is null or missing (image-only source; OCR/manual review required).",
                    field=f,
                    value=v,
                )
                add_once(
                    "LLM_BLANK_AS_MISSING",
                    f"Blank '{f}' may be OCR/LLM missingness from image-only 1040. Enforce schema null rules post-OCR.",
                    field=f,
                    value=v,
                )
            add_once(
                "FLD_ILLEGIBLE",
                f"Field '{f}' is not reliably machine-readable on image-only 1040. Re-run OCR or route to manual review.",
                field=f,
                value=v,
            )

        add_once(
            "LLM_OVER_INFERENCE",
            "Image-only 1040 detected; disable inference mode and require OCR-anchored extraction for empty/uncertain lines.",
            field=None,
            value=None,
        )
        return excs

    def _validate_1040(self, d):
        try:
            excs = []
            excs += self._validate_1040_scan_profile(d, getattr(self, "_ctx", {}))
            excs += self._req(d, ["taxpayer_ssn","total_income","adjusted_gross_income"], "1040")
            excs += self._neg(d, ["total_income","adjusted_gross_income","taxable_income",
                                   "total_withholding","estimated_tax_payments"])
            total = self._f(d, "total_income")
            adj   = self._f(d, "adjustments_to_income") or 0.0
            agi   = self._f(d, "adjusted_gross_income")
            if total is not None and agi is not None:
                expected = round(total - adj, 2)
                diff = abs(expected - agi)
                if diff > MATH_TOLERANCE:
                    excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                        f"1040 Line 11 AGI (${agi:,.2f}) != Line 9 (${total:,.2f}) "
                        f"- Line 10 (${adj:,.2f}) = ${expected:,.2f}. Diff: ${diff:,.2f}.",
                        field="adjusted_gross_income", value=agi))
            ded     = self._f(d, "total_deductions") or 0.0
            taxable = self._f(d, "taxable_income")
            if agi is not None and taxable is not None:
                expected = max(0.0, round(agi - ded, 2))
                diff = abs(expected - taxable)
                if diff > MATH_TOLERANCE:
                    excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                        f"1040 Line 15 Taxable Income (${taxable:,.2f}) != "
                        f"max(0, AGI-Deductions) = ${expected:,.2f}.",
                        field="taxable_income", value=taxable))
            w2 = self._f(d, "withholding_w2") or 0.0
            n99 = self._f(d, "withholding_1099") or 0.0
            other = self._f(d, "withholding_other") or 0.0
            total_wh = self._f(d, "total_withholding")
            if total_wh is not None and (w2 + n99 + other) > 0:
                expected = round(w2 + n99 + other, 2)
                diff = abs(expected - total_wh)
                if diff > MATH_TOLERANCE:
                    excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                        f"1040 Line 25d total withholding (${total_wh:,.2f}) != "
                        f"25a+25b+25c = ${expected:,.2f}.",
                        field="total_withholding", value=total_wh))
            total_tax  = self._f(d, "total_tax")
            total_pmts = self._f(d, "total_payments")
            owed       = self._f(d, "amount_owed")
            overpy     = self._f(d, "overpayment")
            if total_tax is not None and total_pmts is not None:
                balance = round(total_tax - total_pmts, 2)
                if balance > MATH_TOLERANCE and owed is not None:
                    diff = abs(owed - balance)
                    if diff > MATH_TOLERANCE:
                        excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                            f"1040 Amount Owed (${owed:,.2f}) != Total Tax - Payments = ${balance:,.2f}.",
                            field="amount_owed", value=owed))
                elif balance < -MATH_TOLERANCE and overpy is not None:
                    exp_op = abs(balance)
                    if abs(overpy - exp_op) > MATH_TOLERANCE:
                        excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                            f"1040 Overpayment (${overpy:,.2f}) != expected ${exp_op:,.2f}.",
                            field="overpayment", value=overpy))
            if total is not None and agi is not None and agi > total + MATH_TOLERANCE:
                excs.append(self._make_exc("NUM_NEGATIVE_VALUE",
                    f"1040 AGI (${agi:,.2f}) exceeds Total Income (${total:,.2f}).",
                    field="adjusted_gross_income", value=agi))
            if agi is not None and taxable is not None and taxable > agi + MATH_TOLERANCE:
                excs.append(self._make_exc("NUM_NEGATIVE_VALUE",
                    f"1040 Taxable Income (${taxable:,.2f}) exceeds AGI (${agi:,.2f}).",
                    field="taxable_income", value=taxable))
            if total_wh is not None and total is not None and total_wh > total + MATH_TOLERANCE:
                excs.append(self._make_exc("NUM_WITHHOLDING_GT_INC",
                    f"1040 Total Withholding (${total_wh:,.2f}) exceeds Total Income (${total:,.2f}).",
                    field="total_withholding", value=total_wh))
            filing = str(d.get("filing_status","")).strip().lower()
            std = self._f(d, "standard_or_itemized_ded")
            if std is not None and filing in STANDARD_DEDUCTIONS_2026:
                exp_std = STANDARD_DEDUCTIONS_2026[filing]
                if std < exp_std - MATH_TOLERANCE:
                    excs.append(self._make_exc("CTX_FILING_STATUS_DEP",
                        f"1040 Line 12 deduction (${std:,.2f}) < 2026 standard deduction "
                        f"${exp_std:,.2f} for '{filing}'.",
                        field="standard_or_itemized_ded", value=std))
            biz = self._f(d, "business_income")
            sched_c = d.get("schedule_c_attached")
            if biz is not None and biz != 0:
                if not sched_c or str(sched_c).lower() in ("false","no","0",""):
                    excs.append(self._make_exc("CTX_BIZ_NO_SCHED_C",
                        f"1040 shows business income (${biz:,.2f}) but Schedule C absent.",
                        field="business_income", value=biz))
            excs += self._tin_exc(d, "taxpayer_ssn", require_tin=False)
            if d.get("spouse_ssn") is not None:
                excs += self._tin_exc(d, "spouse_ssn", require_tin=False)
                if filing in ("single","head of household","hoh"):
                    excs.append(self._make_exc("CTX_SPOUSE_SINGLE",
                        f"1040 has spouse_ssn but filing_status is '{filing}'.",
                        field="spouse_ssn", value=d.get("spouse_ssn")))
            return excs
        except Exception as e:
            return [self._make_exc("DB_TYPE_CONFLICT",
                f"Validator internal error for 1040: {str(e)}", field=None)]

    def _validate_1099_NEC(self, d):
        try:
            excs = []
            excs += self._req(d, ["nonemployee_compensation","payer_tin","recipient_tin"], "1099-NEC")
            excs += self._neg(d, ["nonemployee_compensation","federal_income_tax_withheld"])
            excs += self._bwcheck(d, "nonemployee_compensation","federal_income_tax_withheld","1099-NEC")
            comp = self._f(d, "nonemployee_compensation")
            if comp is not None and 0 < comp < 600.0:
                excs.append(self._make_exc("STR_SCHEDULE_MISSING",
                    f"1099-NEC Box 1 (${comp:,.2f}) is below the $600 IRS filing threshold.",
                    field="nonemployee_compensation", value=comp))
            excs += self._tin_exc(d, "payer_tin", require_tin=True)
            excs += self._tin_exc(d, "recipient_tin", require_tin=False)
            return excs
        except Exception as e:
            return [self._make_exc("DB_TYPE_CONFLICT",
                f"Validator internal error for 1099-NEC: {str(e)}", field=None)]

    def _validate_1099_INT(self, d):
        try:
            excs = []
            excs += self._req(d, ["interest_income","payer_tin"], "1099-INT")
            excs += self._neg(d, ["interest_income","bond_premium"])
            excs += self._bwcheck(d, "interest_income","federal_income_tax_withheld","1099-INT")
            interest = self._f(d, "interest_income")
            if interest is not None and 0 < interest < 10.0:
                excs.append(self._make_exc("STR_SCHEDULE_MISSING",
                    f"1099-INT Box 1 (${interest:,.2f}) is below the $10 IRS threshold.",
                    field="interest_income", value=interest))
            premium = self._f(d, "bond_premium")
            if interest is not None and premium is not None and premium > interest + MATH_TOLERANCE:
                excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                    f"1099-INT bond premium (${premium:,.2f}) exceeds interest (${interest:,.2f}).",
                    field="bond_premium", value=premium))
            excs += self._tin_exc(d, "payer_tin", require_tin=True)
            excs += self._tin_exc(d, "recipient_tin", require_tin=False)
            return excs
        except Exception as e:
            return [self._make_exc("DB_TYPE_CONFLICT",
                f"Validator internal error for 1099-INT: {str(e)}", field=None)]

    def _validate_1099_DIV(self, d):
        try:
            excs = []
            excs += self._req(d, ["total_ordinary_dividends","payer_tin"], "1099-DIV")
            excs += self._neg(d, ["total_ordinary_dividends","qualified_dividends",
                                   "total_capital_gain_distr"])
            excs += self._bwcheck(d, "total_ordinary_dividends","federal_income_tax_withheld","1099-DIV")
            total = self._f(d, "total_ordinary_dividends")
            if total is not None and 0 < total < 10.0:
                excs.append(self._make_exc("STR_SCHEDULE_MISSING",
                    f"1099-DIV Box 1a (${total:,.2f}) below $10 filing threshold.",
                    field="total_ordinary_dividends", value=total))
            qual = self._f(d, "qualified_dividends")
            if total is not None and qual is not None and qual > total + MATH_TOLERANCE:
                excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                    f"1099-DIV qualified dividends (${qual:,.2f}) > total dividends (${total:,.2f}).",
                    field="qualified_dividends", value=qual))
            total_cg = self._f(d, "total_capital_gain_distr")
            sec1250 = self._f(d, "unrecaptured_sec1250_gain") or 0.0
            sec1202 = self._f(d, "section_1202_gain") or 0.0
            col28   = self._f(d, "collectibles_28pct_gain") or 0.0
            sub = round(sec1250 + sec1202 + col28, 2)
            if total_cg is not None and sub > 0 and sub > total_cg + MATH_TOLERANCE:
                excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                    f"1099-DIV capital gain subcategories (${sub:,.2f}) > Box 2a (${total_cg:,.2f}).",
                    field="total_capital_gain_distr", value=total_cg))
            excs += self._tin_exc(d, "payer_tin", require_tin=True)
            excs += self._tin_exc(d, "recipient_tin", require_tin=False)
            return excs
        except Exception as e:
            return [self._make_exc("DB_TYPE_CONFLICT",
                f"Validator internal error for 1099-DIV: {str(e)}", field=None)]

    def _validate_1099_R(self, d):
        try:
            excs = []
            excs += self._req(d, ["gross_distribution","payer_tin","distribution_code"], "1099-R")
            excs += self._neg(d, ["gross_distribution","federal_income_tax_withheld"])
            gross   = self._f(d, "gross_distribution")
            taxable = self._f(d, "taxable_amount")
            cap_gain= self._f(d, "capital_gain")
            fed_tax = self._f(d, "federal_income_tax_withheld")
            if gross is not None and taxable is not None and taxable > gross + MATH_TOLERANCE:
                excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                    f"1099-R taxable amount (${taxable:,.2f}) > gross distribution (${gross:,.2f}).",
                    field="taxable_amount", value=taxable))
            if taxable is not None and cap_gain is not None and cap_gain > taxable + MATH_TOLERANCE:
                excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                    f"1099-R capital gain (${cap_gain:,.2f}) > taxable amount (${taxable:,.2f}).",
                    field="capital_gain", value=cap_gain))
            if gross is not None and fed_tax is not None and fed_tax > gross + MATH_TOLERANCE:
                excs.append(self._make_exc("NUM_WITHHOLDING_GT_INC",
                    f"1099-R withholding (${fed_tax:,.2f}) > gross distribution (${gross:,.2f}).",
                    field="federal_income_tax_withheld", value=fed_tax))
            code = d.get("distribution_code")
            if code is not None:
                codes = [c.strip().upper() for c in re.split(r'[,/\s]+', str(code)) if c.strip()]
                for c in codes:
                    if c not in VALID_1099R_CODES:
                        excs.append(self._make_exc("DB_TYPE_CONFLICT",
                            f"1099-R Box 7 distribution code '{c}' is not a valid IRS code. "
                            f"Valid codes: {sorted(VALID_1099R_CODES)}",
                            field="distribution_code", value=c))
                if '1' in codes:
                    excs.append(self._make_exc("CTX_FILING_STATUS_DEP",
                        f"1099-R code '1' = early distribution. 10% additional tax (Form 5329) "
                        f"likely applies on ${(gross or 0):,.2f} per IRC 72(t).",
                        field="distribution_code", value="1"))
            excs += self._tin_exc(d, "payer_tin", require_tin=True)
            excs += self._tin_exc(d, "recipient_tin", require_tin=False)
            return excs
        except Exception as e:
            return [self._make_exc("DB_TYPE_CONFLICT",
                f"Validator internal error for 1099-R: {str(e)}", field=None)]

    def _validate_1099_MISC(self, d):
        try:
            excs = []
            excs += self._req(d, ["payer_tin"], "1099-MISC")
            has_income = any(self._f(d, f) is not None and self._f(d, f) > 0
                             for f in INCOME_FIELDS_1099_MISC)
            if not has_income:
                excs.append(self._make_exc("FLD_ZERO_VS_BLANK",
                    "1099-MISC has no income fields populated.",
                    field=None))
            for field, threshold, label in [
                ("rents", 600, "$600"),
                ("royalties", 10, "$10"),
                ("medical_health_care_payments", 600, "$600")
            ]:
                val = self._f(d, field)
                if val is not None and 0 < val < threshold:
                    excs.append(self._make_exc("STR_SCHEDULE_MISSING",
                        f"1099-MISC '{field}' (${val:,.2f}) below {label} threshold.",
                        field=field, value=val))
            excs += self._neg(d, INCOME_FIELDS_1099_MISC)
            excs += self._tin_exc(d, "payer_tin", require_tin=True)
            excs += self._tin_exc(d, "recipient_tin", require_tin=False)
            return excs
        except Exception as e:
            return [self._make_exc("DB_TYPE_CONFLICT",
                f"Validator internal error for 1099-MISC: {str(e)}", field=None)]

    def _validate_1099_B(self, d):
        try:
            excs = []
            excs += self._req(d, ["proceeds","payer_tin"], "1099-B")
            excs += self._neg(d, ["proceeds"])
            proceeds = self._f(d, "proceeds")
            cost     = self._f(d, "cost_or_basis")
            wash     = self._f(d, "wash_sale_loss_disallowed") or 0.0
            if wash > 0 and proceeds is not None and cost is not None and proceeds >= cost:
                excs.append(self._make_exc("NUM_DUPLICATE_ENTRY",
                    f"1099-B wash sale loss (${wash:,.2f}) present but proceeds >= cost "
                    f"(no realized loss). Wash sale only applies to realized losses.",
                    field="wash_sale_loss_disallowed", value=wash))
            if proceeds is not None and cost is not None and proceeds > 0:
                net = proceeds - cost + wash
                if net > proceeds * 2:
                    excs.append(self._make_exc("NUM_DECIMAL_MISPLACE",
                        f"1099-B net gain (${net:,.2f}) > 2x proceeds (${proceeds:,.2f}). "
                        f"Verify cost basis — possible decimal misplacement.",
                        field="cost_or_basis", value=cost))
            excs += self._tin_exc(d, "payer_tin", require_tin=True)
            excs += self._tin_exc(d, "recipient_tin", require_tin=False)
            return excs
        except Exception as e:
            return [self._make_exc("DB_TYPE_CONFLICT",
                f"Validator internal error for 1099-B: {str(e)}", field=None)]

    def _validate_1099_G(self, d):
        try:
            excs = []
            excs += self._req(d, ["payer_tin"], "1099-G")
            uc     = self._f(d, "unemployment_compensation")
            refund = self._f(d, "state_local_tax_refund")
            if uc is None and refund is None:
                excs.append(self._make_exc("FLD_ZERO_VS_BLANK",
                    "1099-G requires unemployment_compensation or state_local_tax_refund.",
                    field=None))
            if uc is not None and uc <= 0:
                excs.append(self._make_exc("NUM_NEGATIVE_VALUE",
                    f"1099-G Box 1 unemployment compensation must be >$0. Got: ${uc:,.2f}",
                    field="unemployment_compensation", value=uc))
            bw = self._f(d, "federal_income_tax_withheld")
            if uc is not None and bw is not None and bw > 0:
                expected = round(uc * 0.10, 2)
                diff = abs(expected - bw)
                if diff > max(MATH_TOLERANCE, uc * 0.05):
                    excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                        f"1099-G withholding (${bw:,.2f}) differs from 10% of UC (${expected:,.2f}).",
                        field="federal_income_tax_withheld", value=bw))
            excs += self._tin_exc(d, "payer_tin", require_tin=True)
            excs += self._tin_exc(d, "recipient_tin", require_tin=False)
            return excs
        except Exception as e:
            return [self._make_exc("DB_TYPE_CONFLICT",
                f"Validator internal error for 1099-G: {str(e)}", field=None)]

    def _validate_1099_K(self, d):
        try:
            excs = []
            excs += self._req(d, ["gross_amount_payment_card","payer_tin"], "1099-K")
            excs += self._neg(d, ["gross_amount_payment_card"])
            gross = self._f(d, "gross_amount_payment_card")
            cnp   = self._f(d, "card_not_present_transactions")
            if gross is not None and cnp is not None and cnp > gross + MATH_TOLERANCE:
                excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                    f"1099-K Box 1b card-not-present (${cnp:,.2f}) > Box 1a gross (${gross:,.2f}).",
                    field="card_not_present_transactions", value=cnp))
            months = ["january","february","march","april","may","june",
                      "july","august","september","october","november","december"]
            monthly = [self._f(d, m) for m in months]
            non_null = [v for v in monthly if v is not None]
            if gross is not None and len(non_null) >= 6:
                monthly_sum = round(sum(non_null), 2)
                if monthly_sum > gross + MATH_TOLERANCE:
                    excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                        f"1099-K partial monthly sum ({len(non_null)} months populated, "
                        f"${monthly_sum:,.2f}) already exceeds Box 1a gross (${gross:,.2f}). "
                        f"Verify extraction of remaining months.",
                        field="gross_amount_payment_card", value=gross))
                elif len(non_null) == 12:
                    diff = abs(monthly_sum - gross)
                    if diff > MATH_TOLERANCE:
                        excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                            f"1099-K monthly sum (${monthly_sum:,.2f}) != Box 1a (${gross:,.2f}).",
                            field="gross_amount_payment_card", value=gross))
            if gross is not None and 0 < gross < 5000:
                excs.append(self._make_exc("STR_SCHEDULE_MISSING",
                    f"1099-K gross (${gross:,.2f}) below 2026 $5,000 threshold.",
                    field="gross_amount_payment_card", value=gross))
            excs += self._tin_exc(d, "payer_tin", require_tin=True)
            excs += self._tin_exc(d, "recipient_tin", require_tin=False)
            return excs
        except Exception as e:
            return [self._make_exc("DB_TYPE_CONFLICT",
                f"Validator internal error for 1099-K: {str(e)}", field=None)]

    def _validate_1099_S(self, d):
        try:
            excs = []
            excs += self._req(d, ["gross_proceeds","payer_tin","date_of_closing"], "1099-S")
            gross = self._f(d, "gross_proceeds")
            if gross is not None and gross <= 0:
                excs.append(self._make_exc("NUM_NEGATIVE_VALUE",
                    f"1099-S Box 2 gross proceeds must be >$0. Got: ${gross:,.2f}",
                    field="gross_proceeds", value=gross))
            excs += self._tin_exc(d, "payer_tin", require_tin=False)
            excs += self._tin_exc(d, "recipient_tin", require_tin=False)
            return excs
        except Exception as e:
            return [self._make_exc("DB_TYPE_CONFLICT",
                f"Validator internal error for 1099-S: {str(e)}", field=None)]

    def _validate_K_1_1065(self, d):
        try:
            excs = []
            excs += self._req(d, ["partnership_tin","partner_tin","ending_capital_account"],
                              "K-1 (1065)")
            beg  = self._f(d, "beginning_capital_account") or 0.0
            cont = self._f(d, "contributions") or 0.0
            inc  = self._f(d, "current_year_net_income") or 0.0
            wdrl = abs(self._f(d, "withdrawals_distributions") or 0.0)
            end  = self._f(d, "ending_capital_account")
            if end is not None:
                expected = round(beg + cont + inc - wdrl, 2)
                diff = abs(expected - end)
                effective_k1_tolerance = max(K1_TOLERANCE, abs(end) * 0.0001)
                if diff > effective_k1_tolerance:
                    excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                        f"K-1 (1065) Box L capital roll-forward mismatch. "
                        f"Beg(${beg:,.2f})+Cont(${cont:,.2f})+Inc(${inc:,.2f})-Wdrl(${wdrl:,.2f})"
                        f"=${expected:,.2f} but Ending=${end:,.2f}. Diff=${diff:,.2f}.",
                        field="ending_capital_account", value=end))
            gp_a = self._f(d, "guaranteed_payments_services") or 0.0
            gp_b = self._f(d, "guaranteed_payments_capital") or 0.0
            gp_t = self._f(d, "total_guaranteed_payments")
            if gp_t is not None and (gp_a + gp_b) > 0:
                expected = round(gp_a + gp_b, 2)
                if abs(expected - gp_t) > MATH_TOLERANCE:
                    excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                        f"K-1 (1065) Box 4c total GP (${gp_t:,.2f}) != 4a+4b=${expected:,.2f}.",
                        field="total_guaranteed_payments", value=gp_t))
            ord_d  = self._f(d, "ordinary_dividends")
            qual_d = self._f(d, "qualified_dividends")
            if ord_d is not None and qual_d is not None and qual_d > ord_d + MATH_TOLERANCE:
                excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                    f"K-1 (1065) qualified dividends (${qual_d:,.2f}) > ordinary (${ord_d:,.2f}).",
                    field="qualified_dividends", value=qual_d))
            pct = self._f(d, "partner_share_percentage")
            if pct is not None and (pct < 0 or pct > 100):
                excs.append(self._make_exc("NUM_NEGATIVE_VALUE",
                    f"K-1 (1065) partner share percentage ({pct}%) must be 0-100.",
                    field="partner_share_percentage", value=pct))
            if end is not None and end < -MATH_TOLERANCE:
                excs.append(self._make_exc("NUM_LARGE_OUTLIER",
                    f"K-1 (1065) ending capital account is negative (${end:,.2f}). Verify with CPA.",
                    field="ending_capital_account", value=end))
            excs += self._tin_exc(d, "partnership_tin", require_tin=True)
            excs += self._tin_exc(d, "partner_tin", require_tin=False)
            return excs
        except Exception as e:
            return [self._make_exc("DB_TYPE_CONFLICT",
                f"Validator internal error for K-1-1065: {str(e)}", field=None)]

    def _validate_K_1_1120S(self, d):
        try:
            excs = []
            excs += self._req(d, ["corporation_tin","shareholder_tin"], "K-1 (1120-S)")
            ord_d  = self._f(d, "ordinary_dividends")
            qual_d = self._f(d, "qualified_dividends")
            if ord_d is not None and qual_d is not None and qual_d > ord_d + MATH_TOLERANCE:
                excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                    f"K-1 (1120-S) qualified dividends (${qual_d:,.2f}) > ordinary (${ord_d:,.2f}).",
                    field="qualified_dividends", value=qual_d))
            pct = self._f(d, "shareholder_share_percentage")
            if pct is not None and (pct < 0 or pct > 100):
                excs.append(self._make_exc("NUM_NEGATIVE_VALUE",
                    f"K-1 (1120-S) shareholder ownership ({pct}%) must be 0-100.",
                    field="shareholder_share_percentage", value=pct))
            income = self._f(d, "ordinary_business_income")
            if income is not None and income < -50000:
                excs.append(self._make_exc("CTX_BIZ_NO_SCHED_C",
                    f"K-1 (1120-S) large S-corp loss (${income:,.2f}). "
                    f"Verify shareholder has sufficient basis (IRC 1366).",
                    field="ordinary_business_income", value=income))
            excs += self._tin_exc(d, "corporation_tin", require_tin=True)
            excs += self._tin_exc(d, "shareholder_tin", require_tin=False)
            return excs
        except Exception as e:
            return [self._make_exc("DB_TYPE_CONFLICT",
                f"Validator internal error for K-1-1120S: {str(e)}", field=None)]

    def _validate_K_1_1041(self, d):
        try:
            excs = []
            excs += self._req(d, ["estate_tin","beneficiary_tin"], "K-1 (1041)")
            ord_d  = self._f(d, "ordinary_dividends")
            qual_d = self._f(d, "qualified_dividends")
            if ord_d is not None and qual_d is not None and qual_d > ord_d + MATH_TOLERANCE:
                excs.append(self._make_exc("NUM_SUBTOTAL_MISMATCH",
                    f"K-1 (1041) qualified dividends (${qual_d:,.2f}) > ordinary (${ord_d:,.2f}).",
                    field="qualified_dividends", value=qual_d))
            final = self._f(d, "final_year_deductions")
            if final is not None and final < 0:
                excs.append(self._make_exc("NUM_NEGATIVE_VALUE",
                    f"K-1 (1041) Box 11 final year deductions (${final:,.2f}) cannot be negative.",
                    field="final_year_deductions", value=final))
            excs += self._tin_exc(d, "estate_tin", require_tin=True)
            excs += self._tin_exc(d, "beneficiary_tin", require_tin=False)
            return excs
        except Exception as e:
            return [self._make_exc("DB_TYPE_CONFLICT",
                f"Validator internal error for K-1-1041: {str(e)}", field=None)]


if __name__ == "__main__":
    engine = ValidationEngine()
    passed = 0
    failed = 0

    def test(name, result, expected_confidence, expected_codes):
        global passed, failed
        actual_codes = {e["code"] for e in result["exceptions"]}
        missing = set(expected_codes) - actual_codes
        if result["confidence"] != expected_confidence or missing:
            print(f"FAIL [{name}]: confidence={result['confidence']} "
                  f"(expected {expected_confidence}), missing codes: {missing}")
            failed += 1
        else:
            print(f"PASS [{name}]")
            passed += 1

    test("FLD_ZERO_VS_BLANK string zero",
        engine.validate("W-2", {"wages_tips_compensation":"0","employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"}),
        "LOW", {"FLD_ZERO_VS_BLANK"})
    test("FLD_DASH_SYMBOL",
        engine.validate("W-2", {"wages_tips_compensation":"\u2014","employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"}),
        "MEDIUM", {"FLD_DASH_SYMBOL", "FLD_SPECIAL_CHARS"})
    test("FLD_NA_TEXT",
        engine.validate("W-2", {"wages_tips_compensation":"N/A","employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"}),
        "MEDIUM", {"FLD_NA_TEXT", "FLD_SPECIAL_CHARS"})
    test("FLD_SPECIAL_CHARS",
        engine.validate("W-2", {"wages_tips_compensation":"54,23I.00","employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"}),
        "MEDIUM", {"FLD_SPECIAL_CHARS"})
    test("NUM_SUBTOTAL_MISMATCH W-2 SS",
        engine.validate("W-2", {"wages_tips_compensation":54231,"social_security_wages":54231,
                                 "social_security_tax_withheld":9999,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"}),
        "MEDIUM", {"NUM_SUBTOTAL_MISMATCH"})
    test("NUM_NEGATIVE_VALUE",
        engine.validate("W-2", {"wages_tips_compensation":-1000,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"}),
        "LOW", {"NUM_NEGATIVE_VALUE"})
    test("NUM_DECIMAL_MISPLACE",
        engine.validate("W-2", {"wages_tips_compensation":15_000_000,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"}),
        "MEDIUM", {"NUM_DECIMAL_MISPLACE"})
    test("NUM_LARGE_OUTLIER",
        engine.validate("W-2", {"wages_tips_compensation":2_000_000,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"}),
        "MEDIUM", {"NUM_LARGE_OUTLIER"})
    test("ID_INVALID_SSN area 000",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"000-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"}),
        "LOW", {"ID_INVALID_SSN"})
    test("ID_INVALID_SSN area 666",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"666-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"}),
        "LOW", {"ID_INVALID_SSN"})
    test("ID_INVALID_SSN area 900+",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"900-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"}),
        "LOW", {"ID_INVALID_SSN"})
    test("ID_INVALID_TIN bad prefix",
        engine.validate("1099-NEC", {"nonemployee_compensation":1000,"payer_tin":"00-1234567",
                                      "recipient_tin":"123-45-6789"}),
        "LOW", {"ID_INVALID_TIN"})
    test("ID_MASKED_SSN",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"***-**-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"}),
        "MEDIUM", {"ID_MASKED_SSN"})
    test("LLM_OVER_NORMALIZATION",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789",
                                 "employer_name":"Acme Corporation","employee_name":"John Smith"}),
        "MEDIUM", {"LLM_OVER_NORMALIZATION"})
    test("OCR_CROPPED",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"},
                         context={"ocr":{"is_cropped":True}}),
        "LOW", {"OCR_CROPPED"})
    test("OCR_CORRUPTED_PDF",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"},
                         context={"ocr":{"is_corrupted":True}}),
        "LOW", {"OCR_CORRUPTED_PDF"})
    test("OCR_LOW_CONFIDENCE",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"},
                         context={"ocr":{"confidence":0.65}}),
        "MEDIUM", {"OCR_LOW_CONFIDENCE"})
    test("EMAIL_SPOOFED",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"},
                         context={"email":{"spoofing_risk_score":0.85,"sender_domain":"fake.com"}}),
        "LOW", {"EMAIL_SPOOFED"})
    test("ENG_UNKNOWN_CLIENT",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"},
                         context={"engagement":{"client_found":False}}),
        "LOW", {"ENG_UNKNOWN_CLIENT"})
    test("MT_CROSS_TENANT_CLIENT",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"},
                         context={"tenant":{"current_tenant_id":"firm_a",
                                            "ssn_tenant_map":{"123-45-6789":"firm_b"}}}),
        "LOW", {"MT_CROSS_TENANT_CLIENT"})
    test("WF_MANUAL_NO_AUDIT",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"},
                         context={"workflow":{"manual_override":True,"audit_trail_present":False}}),
        "LOW", {"WF_MANUAL_NO_AUDIT"})
    test("SEC_TAMPERED_DOC",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"},
                         context={"security":{"document_hash_expected":"abc123",
                                              "document_hash_actual":"def456"}}),
        "LOW", {"SEC_TAMPERED_DOC"})
    test("LLMD_CROSS_CLIENT_BLEED",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"},
                         context={"llm":{"context_client_id":"client_a","extracted_client_id":"client_b"}}),
        "LOW", {"LLMD_CROSS_CLIENT_BLEED"})
    test("XDOC_DUPLICATE_UPLOAD",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y",
                                 "_document_hash":"abc123def456"},
                         context={"session":{"processed_hashes":["abc123def456"]}}),
        "HIGH", {"XDOC_DUPLICATE_UPLOAD"})
    test("CY_CARRYOVER_MISSING",
        engine.validate("1040", {"taxpayer_ssn":"123-45-6789","total_income":80000,
                                  "adjusted_gross_income":80000},
                         context={"session":{"prior_year_estimated_payments":2400}}),
        "MEDIUM", {"CY_CARRYOVER_MISSING"})
    test("LLM_HALLUCINATED",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"},
                         context={"llm":{"hallucinated_fields":["federal_income_tax_withheld"]}}),
        "LOW", {"LLM_HALLUCINATED"})

    # ── Audit-fix regression tests ─────────────────────────────────────────────

    # C3: bwcheck should NOT fire for voluntary 10% withholding (no second_tin_notice)
    test("_bwcheck no false positive voluntary withholding",
        engine.validate("1099-NEC", {"nonemployee_compensation":5000,
                                      "federal_income_tax_withheld":500,
                                      "payer_tin":"12-3456789",
                                      "recipient_tin":"123-45-6789"}),
        "HIGH", set())

    # C3: bwcheck MUST fire when second_tin_notice=True
    test("_bwcheck fires on second_tin_notice",
        engine.validate("1099-NEC", {"nonemployee_compensation":5000,
                                      "federal_income_tax_withheld":500,
                                      "second_tin_notice": True,
                                      "payer_tin":"12-3456789",
                                      "recipient_tin":"123-45-6789"}),
        "MEDIUM", {"NUM_SUBTOTAL_MISMATCH"})

    # C11: LED_CLIENT_WAIVED fires and waived form excluded from LED_PARTIAL_FORM_SET
    test("LED_CLIENT_WAIVED fires",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y"},
                         context={"workflow":{"client_waived_forms":["W-2"],
                                              "forms_in_ledger":["W-2","1099-INT"]}}),
        "HIGH", {"LED_CLIENT_WAIVED"})

    # C10: ID_NAME_TIN_MISMATCH fires when name doesn't fuzzily match known TIN
    test("ID_NAME_TIN_MISMATCH fires",
        engine.validate("W-2", {"wages_tips_compensation":54231,"employee_ssn":"123-45-6789",
                                 "employer_tin":"12-3456789",
                                 "employer_name":"Totally Different Corp","employee_name":"Y"},
                         context={"engagement":{"client_found":True,
                                                "known_tin_name_map":{"12-3456789":"Acme Inc"}}}),
        "MEDIUM", {"ID_NAME_TIN_MISMATCH"})

    # C4: CY_WRONG_YEAR_UPLOAD should fire exactly ONCE for W-2 with bad year (no double-fire)
    result_bad_year = engine.validate("W-2",
        {"wages_tips_compensation":54231,"employee_ssn":"123-45-6789",
         "employer_tin":"12-3456789","employer_name":"X","employee_name":"Y","tax_year":2010})
    year_exc_count = sum(1 for e in result_bad_year["exceptions"]
                         if e["code"] == "CY_WRONG_YEAR_UPLOAD")
    if year_exc_count == 1:
        print("PASS  CY_WRONG_YEAR_UPLOAD fires exactly once on W-2 bad year")
        passed += 1
    else:
        print(f"FAIL  CY_WRONG_YEAR_UPLOAD fired {year_exc_count}x (expected 1)")
        failed += 1


    print(f"\n{'='*60}")
    total = passed + failed
    print(f"Results: {passed}/{total} passed, {failed} failed")
    if failed == 0:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
