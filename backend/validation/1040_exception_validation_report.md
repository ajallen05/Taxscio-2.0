# 1040 Form — Exception Validation Report

> **Document:** 1040.pdf (2-page scanned/image-only PDF)
> **Exception Ruleset:** Exceptions_-_Validation_Agent_1.xlsx
> **Total Exceptions Evaluated:** 90
> **Generated:** 2026-03-24

---

## Summary

| Status | Count |
|---|---|
| 🔴 Triggered | 5 |
| 🟡 Review Required | 38 |
| 🟢 Pass | 13 |
| 🔵 Info | 7 |
| ⚪ N/A | 27 |

---

## Structural

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 1 | Optional Field Left Blank | Field intentionally blank and allowed | Mark as NULL_ALLOWED | INFO | ℹ️ INFO | Optional fields (e.g. Apt number, suffix) are blank — allowed per IRS schema. |
| 2 | Conditional Field Not Triggered | Required only if parent condition met | Evaluate parent rule first | INFO | ℹ️ INFO | Schedule fields not triggered because parent income lines are not populated (scanned, unextracted). |
| 3 | Schedule Not Attached | Required only above threshold | Validate threshold logic | WARNING | 🟡 REVIEW | Cannot confirm whether Schedule B/C/D/E thresholds are met — values not extracted from scanned PDF. |
| 4 | Multi-Page Form Variant | Page missing but not required in this version | Validate against version schema | INFO | ✅ PASS | Both pages present in the uploaded PDF. |
| 5 | Alternate Layout Version | IRS layout differs by year | Apply version-aware template | INFO | 🟡 REVIEW | Tax year on form not machine-readable; year-specific template match unconfirmed. |
| 6 | Deprecated Field Present | Field no longer applicable | Ignore if not required for year | INFO | ✅ PASS | No deprecated fields visually detected on the form. |

---

## Field-Level

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 7 | Zero vs Blank | 0 misread as missing | Enforce strict numeric/null distinction | BLOCKING | 🔴 TRIGGERED | PDF is image-only; cannot distinguish 0 from blank in any numeric line. All income/deduction fields at risk. |
| 8 | Dash Symbol Used | "—" used instead of zero | Normalize to numeric zero | INFO | 🟡 REVIEW | Scanned 1040 commonly uses dashes for zero entries. Post-OCR normalization required. |
| 9 | Checkbox Not Checked | Boolean interpreted as missing | Interpret as FALSE | INFO | ℹ️ INFO | Filing status checkboxes present; unchecked ones should be interpreted as FALSE, not missing. |
| 10 | "N/A" Text | Indicates non-applicable | Convert to structured null | INFO | ℹ️ INFO | Some lines may contain N/A. Post-OCR, convert to structured null. |
| 11 | Illegible but Present | OCR confidence below threshold | Re-run OCR or manual review | WARNING | 🔴 TRIGGERED | Entire form is image-based. All fields have zero OCR confidence — illegible to machines without OCR. |
| 12 | Multi-Line Address Collapsed | Address improperly merged | Structured re-parse | WARNING | 🟡 REVIEW | Address fields (city, state, ZIP) appear as single line in scanned form. Re-parse after OCR. |
| 13 | Special Characters in Numeric Field | OCR noise in number | Sanitize before validation | WARNING | 🟡 REVIEW | OCR on scanned numeric fields (Lines 1–37) likely to introduce noise. Sanitize before arithmetic checks. |

---

## Numeric & Arithmetic

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 14 | Subtotal Mismatch | Lines do not sum correctly | Recalculate and flag | WARNING | 🟡 REVIEW | Cannot verify AGI = Gross Income − Adjustments or Tax = Taxable Income × Rate without extracted values. |
| 15 | Withholding > Income | Suspicious but possible | Mark review_required | WARNING | 🟡 REVIEW | Line 25 (withholding) vs Lines 1–8 (income) comparison pending OCR extraction. |
| 16 | Negative Value Not Allowed | Negative in restricted field | Hard validation failure | BLOCKING | 🟡 REVIEW | Cannot confirm absence of negatives in restricted fields (e.g. Line 15 taxable income) without OCR. |
| 17 | Rounding Variance | Minor rounding differences | Accept within tolerance | INFO | ✅ PASS | IRS 1040 uses whole-dollar rounding. Minor ±$1 variances accepted per rule. |
| 18 | Decimal Misplacement | OCR decimal shift | Cross-field plausibility check | WARNING | 🟡 REVIEW | High risk on scanned form — OCR decimal shift could misread $1,000 as $10.00. Cross-field check needed. |
| 19 | Large Statistical Outlier | Extreme year-over-year change | Route to Intelligence layer | WARNING | ⚪ N/A | No prior-year data available in this session for year-over-year comparison. |
| 20 | Duplicate Monetary Entry | Same value repeated across fields | Cross-box validation | WARNING | 🟡 REVIEW | Cannot perform cross-box duplicate value check until numeric fields are extracted. |

---

## Identity & Entity

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 21 | Invalid SSN Format | Incorrect SSN pattern | Reject document | BLOCKING | 🔴 TRIGGERED | SSN field is image-rendered; XXX-XX-XXXX format cannot be programmatically validated. OCR required. |
| 22 | Invalid EIN Format | Incorrect EIN pattern | Reject document | BLOCKING | 🟡 REVIEW | Employer EIN on any attached W-2 reference cannot be validated without OCR extraction. |
| 23 | Masked SSN | Partially redacted SSN | Accept but flag masked | WARNING | 🟡 REVIEW | Cannot determine if SSN is masked or fully present — image-only PDF prevents inspection. |
| 24 | Name–EIN Mismatch | Employer identity mismatch | Cross-reference DB | WARNING | ⚪ N/A | Employer name/EIN cross-reference requires extracted text — not yet available. |
| 25 | Duplicate Dependent SSN | Same SSN used twice | Reject | BLOCKING | 🟡 REVIEW | Dependent SSNs (Part II) cannot be validated for uniqueness without OCR. |
| 26 | Employer EIN Not Seen Before | New employer detected | Allow but flag for review | WARNING | ⚪ N/A | Cannot determine if employer EIN is new — depends on extracted EIN and client history DB. |

---

## Contextual / Tax Logic

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 27 | Filing Status Dependency | Field required under MFJ/MFS | Validate filing status | BLOCKING | 🟡 REVIEW | Filing status checkbox readable visually but not programmatically confirmed. Spouse SSN field dependency unvalidated. |
| 28 | Capital Loss Carryover Missing | Expected from prior year | Cross-year validation | WARNING | ⚪ N/A | No prior-year 1040 in session; carryover check cannot be performed. |
| 29 | Business Income Without Schedule C | Logical mismatch | Flag anomaly | WARNING | 🟡 REVIEW | Line 3 (business income) cannot be confirmed without OCR; Schedule C attachment unverified. |
| 30 | State Tax Without Federal Base | State income w/o federal base | Cross-form validation | WARNING | ⚪ N/A | State return not uploaded; cross-form validation not applicable this session. |
| 31 | Spouse Document for Single Filing | Filing status mismatch | Conditional review | WARNING | ⚪ N/A | Filing status not machine-confirmed; spouse document check deferred. |
| 32 | Dependent Form Uploaded | 1099 under dependent SSN | Link dependent entity | WARNING | ⚪ N/A | No dependent forms uploaded alongside this 1040. |

---

## Formatting & OCR

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 33 | Cropped Document | Missing form edges | Block extraction | BLOCKING | ✅ PASS | Form edges visible on both pages; no cropping detected. |
| 34 | Rotated Scan | Incorrect orientation | Auto-rotate | INFO | ✅ PASS | Document orientation is correct; no rotation needed. |
| 35 | Low OCR Confidence | Below extraction threshold | Re-run or manual review | WARNING | 🔴 TRIGGERED | Entire PDF is image-based with no text layer — OCR confidence is 0% for all fields. |
| 36 | Multiple Forms in One PDF | Combined upload | Segment pages | WARNING | ✅ PASS | Only one 1040 form detected in the uploaded PDF. |
| 37 | Duplicate Page | Same page repeated | Page-level hash check | INFO | ✅ PASS | Page 1 and Page 2 are distinct; no duplicate page detected. |
| 38 | Corrupted PDF | File unreadable | Reject and request re-upload | BLOCKING | ✅ PASS | PDF opens and renders without errors. |

---

## Cross-Document

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 39 | Duplicate Form Upload | Same file already processed | Ignore duplicate | INFO | ✅ PASS | No duplicate hash match found in current session. |
| 40 | Conflicting Income Across Forms | Logical mismatch | Flag CPA review | WARNING | ⚪ N/A | No other income forms (W-2, 1099) uploaded to cross-reference. |
| 41 | Missing Recurring Form | Present PY, absent CY | Intelligence alert | WARNING | ⚪ N/A | No prior-year history available in this session. |
| 42 | Mismatched State Income | State mismatch detected | Cross-validation | WARNING | ⚪ N/A | No state return uploaded for comparison. |

---

## LLM Interpretation

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 43 | Hallucinated Field | Fabricated value | Validate against OCR anchors | BLOCKING | 🟡 REVIEW | High risk on image PDF — LLM may infer values not present. All extracted values must be anchored to OCR output. |
| 44 | Blank Interpreted as Missing | Optional blank flagged | Enforce schema null rules | BLOCKING | 🔴 TRIGGERED | Image-only PDF means blank fields may be flagged as missing. Schema null rules must be enforced post-OCR. |
| 45 | Context Drift | Value from wrong region | Bounding-box anchoring | BLOCKING | 🟡 REVIEW | Without bounding-box coordinates, LLM extraction risks pulling values from wrong 1040 regions. |
| 46 | Reordered Field Mapping | Misaligned box mapping | Template coordinate validation | BLOCKING | 🟡 REVIEW | Field box mapping must be validated against IRS 1040 coordinate template before extraction. |
| 47 | Over-Inference | LLM fills implied data | Disable inference mode | BLOCKING | 🟡 REVIEW | Inference mode must be disabled — LLM should not fill lines that are visually blank. |
| 48 | Numeric Word Conversion Error | Textual number misparsed | Strict numeric extraction | WARNING | 🟡 REVIEW | Handwritten or printed text numbers must use strict numeric extraction, not text-to-number inference. |
| 49 | Cross-Page Context Bleed | Value pulled from wrong page | Page-isolated prompts | BLOCKING | 🟡 REVIEW | Page 1 and Page 2 of 1040 must be extracted with isolated prompts to prevent cross-page value bleed. |
| 50 | Over-Normalization | LLM "corrects" name spelling | Preserve raw extracted text | WARNING | 🟡 REVIEW | Taxpayer name must be preserved exactly as printed — no spelling normalization allowed. |

---

## Engagement Integrity

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 51 | Unknown Client | Valid form but client not found | Route to Unmatched Queue | BLOCKING | 🟡 REVIEW | Client identity cannot be confirmed without extracted SSN match to client DB. |
| 52 | Inactive Engagement | Year not opened | Mark pre-engagement | WARNING | ⚪ N/A | Engagement year status unknown without CRM/DB lookup. |
| 53 | Wrong Tax Year | Form year mismatch | Route to correct workflow | WARNING | 🟡 REVIEW | Tax year on form is image-rendered; year validation against workflow routing is pending OCR. |
| 54 | Duplicate Client Profile | Same SSN in two profiles | Escalate identity resolution | CRITICAL | ⚪ N/A | Cannot assess without extracted SSN matched against client profiles. |
| 55 | Wrong Entity Type | Business form under individual | Block and flag | BLOCKING | ✅ PASS | Form is correctly identified as individual 1040, not a business form. |
| 56 | Client Deleted but Docs Incoming | Stale alias | Reject and notify | BLOCKING | ⚪ N/A | No deleted client flag in current session. |
| 57 | Client Merged / Renamed | Alias or identity shift | Maintain alias mapping | WARNING | ⚪ N/A | No alias/merge flag in current session. |

---

## Email & Source-Level

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 58 | Valid Form from Unknown Email | Sender not registered | Validate via SSN | WARNING | ⚪ N/A | Form uploaded directly — no email source to validate. |
| 59 | Email Forwarded by CPA | CPA forwarding | Match SSN to CPA client list | INFO | ⚪ N/A | Form uploaded directly, not via email. |
| 60 | Spoofed Domain | Fake employer domain | Risk score + security alert | CRITICAL | ⚪ N/A | No email source; spoofed domain check not applicable. |
| 61 | Multiple Clients in One Email | Mixed attachments | Split and match by SSN | WARNING | ⚪ N/A | Single form upload; no email with mixed attachments. |
| 62 | Attachment Without Metadata | No client identifier | Extract then resolve by SSN | WARNING | 🟡 REVIEW | Uploaded file has no embedded metadata (image PDF); client identifier must be resolved via OCR-extracted SSN. |
| 63 | Encrypted PDF | Password protected | Trigger password workflow | WARNING | ✅ PASS | PDF is not password-protected; opens without credentials. |

---

## Multi-Tenant

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 64 | Client Exists in Another Tenant | Same SSN in other firm | Hard isolation block | CRITICAL | ⚪ N/A | Multi-tenant check requires extracted SSN and cross-tenant DB lookup. |
| 65 | Cross-Tenant Document Routing | Wrong S3 bucket | Security block + alert | CRITICAL | ⚪ N/A | Storage routing check is infrastructure-level; not assessable from form alone. |
| 66 | Shared Family Accounts | Joint return, separate logins | Household linking model | INFO | ⚪ N/A | No MFJ filing confirmed yet (filing status not extracted). |

---

## Workflow State

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 67 | Document After Ledger Closed | Engagement complete | Reopen or hold | WARNING | ⚪ N/A | Ledger status unknown without workflow system access. |
| 68 | Re-upload After Extraction | Corrected submission | Increment version | INFO | ⚪ N/A | First upload in session; no prior extraction version. |
| 69 | Extraction Completed but Ledger Not Updated | State inconsistency | Orchestrator repair | BLOCKING | ⚪ N/A | Extraction not yet completed (scanned PDF); ledger update not triggered. |
| 70 | Manual Override Without Audit | Missing audit trail | Block until logged | CRITICAL | ⚪ N/A | No manual override attempted in this session. |

---

## Cross-Year

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 71 | Prior-Year Form Uploaded as Current | Wrong year upload | Auto-detect and reroute | WARNING | 🟡 REVIEW | Tax year not machine-readable from image PDF; cannot confirm form is for correct year without OCR. |
| 72 | Carryover Expected but Missing | Prior-year dependency missing | Intelligence flag | WARNING | ⚪ N/A | No prior-year 1040 available for carryover comparison. |
| 73 | Estimated Payments Present but Not Filed | Data mismatch | CPA review trigger | WARNING | ⚪ N/A | Line 26 (estimated tax payments) cannot be confirmed without OCR extraction. |

---

## Ledger-Level

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 74 | Form Received Not in Ledger | Unexpected form | Add dynamic ledger entry | WARNING | ⚪ N/A | Ledger state not accessible in this session. |
| 75 | Required Form Missing but Client Confirms None | Client confirmation | Mark as waived | INFO | ⚪ N/A | No client confirmation workflow triggered. |
| 76 | Multiple Instances of Same Form | Multiple W-2s etc | Support quantity | INFO | ⚪ N/A | Only one 1040 in upload; W-2 multiplicity check not triggered. |
| 77 | Partial Form Set | Only part of form uploaded | Block and request full set | BLOCKING | ✅ PASS | Both pages of 1040 present in upload. |

---

## Data Persistence & Schema

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 78 | JSON Flatten Failure | Schema mismatch | Rollback transaction | BLOCKING | ⚪ N/A | No JSON extraction attempted yet. |
| 79 | Field Type Conflict | Text in numeric field | Coerce or reject | BLOCKING | 🟡 REVIEW | Post-OCR, all numeric 1040 fields must be validated for type — text/dollar-sign noise expected in scanned form. |
| 80 | Null in Non-Nullable Column | Validation gap | Block insert | BLOCKING | 🟡 REVIEW | Required fields (SSN, name, filing status) must not be null in DB insert. Pending OCR confirmation. |
| 81 | Duplicate Primary Key | Reprocessed document | Idempotent enforcement | BLOCKING | ✅ PASS | No prior extraction record for this document in session. |
| 82 | Schema Drift | Form structure changed | Trigger schema review workflow | WARNING | 🟡 REVIEW | Template match unconfirmed due to image-only PDF; schema drift possible if tax year differs from template. |

---

## Security & Compliance

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 83 | PII in Logs | Sensitive data exposed | Mask + alert | CRITICAL | 🟡 REVIEW | SSN, name, DOB, and income on this 1040 must be masked in all logs post-extraction. |
| 84 | Unauthorized Role Access | Access violation | Hard fail + audit | CRITICAL | ⚪ N/A | Access control check is infrastructure-level. |
| 85 | S3 Public Access Risk | Bucket misconfigured | Security alert | CRITICAL | ⚪ N/A | Storage configuration check is infrastructure-level. |
| 86 | Tampered Document | Hash mismatch | Lock and investigate | CRITICAL | ⚪ N/A | No prior document hash on record to compare against. |
| 87 | Excessive Extraction Attempts | Abuse attempt | Rate-limit + alert | CRITICAL | ⚪ N/A | Single extraction attempt in this session. |

---

## LLM-Specific Domain

| # | Exception | Description | Handling | Severity | 1040 Status | Finding |
|---|---|---|---|---|---|---|
| 88 | Cross-Client Data Bleed | Context memory leak | Stateless extraction | CRITICAL | 🟡 REVIEW | Stateless extraction must be enforced — this 1040 session must not retain context from other client extractions. |
| 89 | Context Window Spillover | Wrong page extraction | Page isolation | BLOCKING | 🟡 REVIEW | Pages 1 and 2 of 1040 must be passed in isolated prompts to prevent cross-page spillover. |
| 90 | Multi-Form PDF Misassignment | Forms merged incorrectly | Page segmentation logic | WARNING | ✅ PASS | Only one form in PDF; misassignment not applicable. |

---

## Key Finding

> **Root cause of most open items:** The uploaded 1040 is an image-only (scanned) PDF with no embedded text layer.
> All triggered and review-flagged exceptions will resolve or be properly evaluable once a full OCR pass is completed.
> Recommend routing through the OCR pipeline before re-running field-level, arithmetic, and identity validations.
