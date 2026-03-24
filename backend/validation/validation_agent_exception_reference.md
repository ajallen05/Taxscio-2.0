# Validation Agent — Exception Reference

> **Source:** Exceptions_-_Validation_Agent_1.xlsx
> **Total Exceptions:** 90 across 15 categories

---

## Severity Legend

| Severity | Meaning |
|---|---|
| `BLOCKING` | Hard stop — must be resolved before processing continues |
| `CRITICAL` | Escalation required — security, compliance, or identity risk |
| `WARNING` | Review recommended — possible issue, not an automatic block |
| `INFO` | Logged and allowed — no action required |

---

## Summary by Category

| # | Category | Exceptions |
|---|---|---|
| 1 | [Structural](#structural) | 6 |
| 2 | [Field-Level](#field-level) | 7 |
| 3 | [Numeric & Arithmetic](#numeric--arithmetic) | 7 |
| 4 | [Identity & Entity](#identity--entity) | 6 |
| 5 | [Contextual / Tax Logic](#contextual--tax-logic) | 6 |
| 6 | [Formatting & OCR](#formatting--ocr) | 6 |
| 7 | [Cross-Document](#cross-document) | 4 |
| 8 | [LLM Interpretation](#llm-interpretation) | 8 |
| 9 | [Engagement Integrity](#engagement-integrity) | 7 |
| 10 | [Email & Source-Level](#email--source-level) | 6 |
| 11 | [Multi-Tenant](#multi-tenant) | 3 |
| 12 | [Workflow State](#workflow-state) | 4 |
| 13 | [Cross-Year](#cross-year) | 3 |
| 14 | [Ledger-Level](#ledger-level) | 4 |
| 15 | [Data Persistence & Schema](#data-persistence--schema) | 5 |
| 16 | [Security & Compliance](#security--compliance) | 5 |
| 17 | [LLM-Specific Domain](#llm-specific-domain) | 3 |

---

## Structural

| Exception | Description | Handling | Severity |
|---|---|---|---|
| Optional Field Left Blank | Field intentionally blank and allowed | Mark as NULL_ALLOWED | `INFO` |
| Conditional Field Not Triggered | Required only if parent condition met | Evaluate parent rule first | `INFO` |
| Schedule Not Attached | Required only above threshold | Validate threshold logic | `WARNING` |
| Multi-Page Form Variant | Page missing but not required in this version | Validate against version schema | `INFO` |
| Alternate Layout Version | IRS layout differs by year | Apply version-aware template | `INFO` |
| Deprecated Field Present | Field no longer applicable | Ignore if not required for year | `INFO` |

---

## Field-Level

| Exception | Description | Handling | Severity |
|---|---|---|---|
| Zero vs Blank | 0 misread as missing | Enforce strict numeric/null distinction | `BLOCKING` |
| Dash Symbol Used | "—" used instead of zero | Normalize to numeric zero | `INFO` |
| Checkbox Not Checked | Boolean interpreted as missing | Interpret as FALSE | `INFO` |
| "N/A" Text | Indicates non-applicable | Convert to structured null | `INFO` |
| Illegible but Present | OCR confidence below threshold | Re-run OCR or manual review | `WARNING` |
| Multi-Line Address Collapsed | Address improperly merged | Structured re-parse | `WARNING` |
| Special Characters in Numeric Field | OCR noise in number | Sanitize before validation | `WARNING` |

---

## Numeric & Arithmetic

| Exception | Description | Handling | Severity |
|---|---|---|---|
| Subtotal Mismatch | Lines do not sum correctly | Recalculate and flag | `WARNING` |
| Withholding > Income | Suspicious but possible | Mark review_required | `WARNING` |
| Negative Value Not Allowed | Negative in restricted field | Hard validation failure | `BLOCKING` |
| Rounding Variance | Minor rounding differences | Accept within tolerance | `INFO` |
| Decimal Misplacement | OCR decimal shift | Cross-field plausibility check | `WARNING` |
| Large Statistical Outlier | Extreme year-over-year change | Route to Intelligence layer | `WARNING` |
| Duplicate Monetary Entry | Same value repeated across fields | Cross-box validation | `WARNING` |

---

## Identity & Entity

| Exception | Description | Handling | Severity |
|---|---|---|---|
| Invalid SSN Format | Incorrect SSN pattern | Reject document | `BLOCKING` |
| Invalid EIN Format | Incorrect EIN pattern | Reject document | `BLOCKING` |
| Masked SSN | Partially redacted SSN | Accept but flag masked | `WARNING` |
| Name–EIN Mismatch | Employer identity mismatch | Cross-reference DB | `WARNING` |
| Duplicate Dependent SSN | Same SSN used twice | Reject | `BLOCKING` |
| Employer EIN Not Seen Before | New employer detected | Allow but flag for review | `WARNING` |

---

## Contextual / Tax Logic

| Exception | Description | Handling | Severity |
|---|---|---|---|
| Filing Status Dependency | Field required under MFJ/MFS | Validate filing status | `BLOCKING` |
| Capital Loss Carryover Missing | Expected from prior year | Cross-year validation | `WARNING` |
| Business Income Without Schedule C | Logical mismatch | Flag anomaly | `WARNING` |
| State Tax Without Federal Base | State income w/o federal base | Cross-form validation | `WARNING` |
| Spouse Document for Single Filing | Filing status mismatch | Conditional review | `WARNING` |
| Dependent Form Uploaded | 1099 under dependent SSN | Link dependent entity | `WARNING` |

---

## Formatting & OCR

| Exception | Description | Handling | Severity |
|---|---|---|---|
| Cropped Document | Missing form edges | Block extraction | `BLOCKING` |
| Rotated Scan | Incorrect orientation | Auto-rotate | `INFO` |
| Low OCR Confidence | Below extraction threshold | Re-run or manual review | `WARNING` |
| Multiple Forms in One PDF | Combined upload | Segment pages | `WARNING` |
| Duplicate Page | Same page repeated | Page-level hash check | `INFO` |
| Corrupted PDF | File unreadable | Reject and request re-upload | `BLOCKING` |

---

## Cross-Document

| Exception | Description | Handling | Severity |
|---|---|---|---|
| Duplicate Form Upload | Same file already processed | Ignore duplicate | `INFO` |
| Conflicting Income Across Forms | Logical mismatch | Flag CPA review | `WARNING` |
| Missing Recurring Form | Present PY, absent CY | Intelligence alert | `WARNING` |
| Mismatched State Income | State mismatch detected | Cross-validation | `WARNING` |

---

## LLM Interpretation

| Exception | Description | Handling | Severity |
|---|---|---|---|
| Hallucinated Field | Fabricated value | Validate against OCR anchors | `BLOCKING` |
| Blank Interpreted as Missing | Optional blank flagged | Enforce schema null rules | `BLOCKING` |
| Context Drift | Value from wrong region | Bounding-box anchoring | `BLOCKING` |
| Reordered Field Mapping | Misaligned box mapping | Template coordinate validation | `BLOCKING` |
| Over-Inference | LLM fills implied data | Disable inference mode | `BLOCKING` |
| Numeric Word Conversion Error | Textual number misparsed | Strict numeric extraction | `WARNING` |
| Cross-Page Context Bleed | Value pulled from wrong page | Page-isolated prompts | `BLOCKING` |
| Over-Normalization | LLM "corrects" name spelling | Preserve raw extracted text | `WARNING` |

---

## Engagement Integrity

| Exception | Description | Handling | Severity |
|---|---|---|---|
| Unknown Client | Valid form but client not found | Route to Unmatched Queue | `BLOCKING` |
| Inactive Engagement | Year not opened | Mark pre-engagement | `WARNING` |
| Wrong Tax Year | Form year mismatch | Route to correct workflow | `WARNING` |
| Duplicate Client Profile | Same SSN in two profiles | Escalate identity resolution | `CRITICAL` |
| Wrong Entity Type | Business form under individual | Block and flag | `BLOCKING` |
| Client Deleted but Docs Incoming | Stale alias | Reject and notify | `BLOCKING` |
| Client Merged / Renamed | Alias or identity shift | Maintain alias mapping | `WARNING` |

---

## Email & Source-Level

| Exception | Description | Handling | Severity |
|---|---|---|---|
| Valid Form from Unknown Email | Sender not registered | Validate via SSN | `WARNING` |
| Email Forwarded by CPA | CPA forwarding | Match SSN to CPA client list | `INFO` |
| Spoofed Domain | Fake employer domain | Risk score + security alert | `CRITICAL` |
| Multiple Clients in One Email | Mixed attachments | Split and match by SSN | `WARNING` |
| Attachment Without Metadata | No client identifier | Extract then resolve by SSN | `WARNING` |
| Encrypted PDF | Password protected | Trigger password workflow | `WARNING` |

---

## Multi-Tenant

| Exception | Description | Handling | Severity |
|---|---|---|---|
| Client Exists in Another Tenant | Same SSN in other firm | Hard isolation block | `CRITICAL` |
| Cross-Tenant Document Routing | Wrong S3 bucket | Security block + alert | `CRITICAL` |
| Shared Family Accounts | Joint return, separate logins | Household linking model | `INFO` |

---

## Workflow State

| Exception | Description | Handling | Severity |
|---|---|---|---|
| Document After Ledger Closed | Engagement complete | Reopen or hold | `WARNING` |
| Re-upload After Extraction | Corrected submission | Increment version | `INFO` |
| Extraction Completed but Ledger Not Updated | State inconsistency | Orchestrator repair | `BLOCKING` |
| Manual Override Without Audit | Missing audit trail | Block until logged | `CRITICAL` |

---

## Cross-Year

| Exception | Description | Handling | Severity |
|---|---|---|---|
| Prior-Year Form Uploaded as Current | Wrong year upload | Auto-detect and reroute | `WARNING` |
| Carryover Expected but Missing | Prior-year dependency missing | Intelligence flag | `WARNING` |
| Estimated Payments Present but Not Filed | Data mismatch | CPA review trigger | `WARNING` |

---

## Ledger-Level

| Exception | Description | Handling | Severity |
|---|---|---|---|
| Form Received Not in Ledger | Unexpected form | Add dynamic ledger entry | `WARNING` |
| Required Form Missing but Client Confirms None | Client confirmation | Mark as waived | `INFO` |
| Multiple Instances of Same Form | Multiple W-2s etc | Support quantity | `INFO` |
| Partial Form Set | Only part of form uploaded | Block and request full set | `BLOCKING` |

---

## Data Persistence & Schema

| Exception | Description | Handling | Severity |
|---|---|---|---|
| JSON Flatten Failure | Schema mismatch | Rollback transaction | `BLOCKING` |
| Field Type Conflict | Text in numeric field | Coerce or reject | `BLOCKING` |
| Null in Non-Nullable Column | Validation gap | Block insert | `BLOCKING` |
| Duplicate Primary Key | Reprocessed document | Idempotent enforcement | `BLOCKING` |
| Schema Drift | Form structure changed | Trigger schema review workflow | `WARNING` |

---

## Security & Compliance

| Exception | Description | Handling | Severity |
|---|---|---|---|
| PII in Logs | Sensitive data exposed | Mask + alert | `CRITICAL` |
| Unauthorized Role Access | Access violation | Hard fail + audit | `CRITICAL` |
| S3 Public Access Risk | Bucket misconfigured | Security alert | `CRITICAL` |
| Tampered Document | Hash mismatch | Lock and investigate | `CRITICAL` |
| Excessive Extraction Attempts | Abuse attempt | Rate-limit + alert | `CRITICAL` |

---

## LLM-Specific Domain

| Exception | Description | Handling | Severity |
|---|---|---|---|
| Cross-Client Data Bleed | Context memory leak | Stateless extraction | `CRITICAL` |
| Context Window Spillover | Wrong page extraction | Page isolation | `BLOCKING` |
| Multi-Form PDF Misassignment | Forms merged incorrectly | Page segmentation logic | `WARNING` |
