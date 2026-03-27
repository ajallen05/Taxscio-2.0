"""
seed_1040_clients.py
════════════════════
Single-file seed script for testing the 1040 → Document Checklist flow.

Creates 5 realistic clients with:
  • Full client record (POST /clients)
  • TY2025 1040 extracted JSON  → saved to local_extraction/ (POST /save-snapshot)
  • TY2025 1040 ledger entry    → POST /ledger/submit
  • TY2025 supporting docs      → POST /ledger/submit  (prior-year for comparison)
  • TY2026 partially submitted  → POST /ledger/submit  (current-year progress)
  • Document checklist derived  → POST /clients/{id}/document-checklist/derive-from-1040

Run with the backend server running:
    python seed_1040_clients.py [--base http://host:8000]

Safe to re-run: the script skips a client if that name already exists.
"""

import argparse, json, sys, time
import requests

# ── CLI ───────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--base", default="http://127.0.0.1:8000",
                    help="Backend base URL (default: http://127.0.0.1:8000)")
args = parser.parse_args()
BASE = args.base.rstrip("/")

print(f"Using backend: {BASE}\n")

# ── Helpers ───────────────────────────────────────────────────────────────────
def _req(method, path, **kwargs):
    url = f"{BASE}{path}"
    try:
        r = getattr(requests, method)(url, timeout=15, **kwargs)
    except requests.ConnectionError:
        print(f"  ✗ Cannot reach {url}. Is the backend running?")
        sys.exit(1)
    return r

def post(path, payload):
    r = _req("post", path, json=payload)
    if r.status_code not in (200, 201):
        print(f"  ✗ POST {path} → {r.status_code}: {r.text[:200]}")
        return None
    return r.json()

def ledger_submit(entry):
    r = _req("post", "/ledger/submit", json=entry)
    ok = r.status_code == 200
    if not ok:
        print(f"    ✗ ledger/submit → {r.status_code}")
    return ok

def save_snapshot(doc_id, form_type, filename, pdf_type, data, exceptions,
                  document_confidence, field_confidence):
    payload = {
        "document_id":         doc_id,
        "form_type":           form_type,
        "filename":            filename,
        "pdf_type":            pdf_type,
        "data":                data,
        "exceptions":          exceptions,
        "document_confidence": document_confidence,
        "field_confidence":    field_confidence,
    }
    r = _req("post", "/save-snapshot", json=payload)
    return r.status_code == 200

def derive_checklist(client_id, tax_year, extracted_fields, field_confidence):
    payload = {
        "tax_year":            tax_year,
        "extracted_fields":    extracted_fields,
        "field_confidence_map": field_confidence,
        "document_type":       "digital",
    }
    r = _req("post", f"/clients/{client_id}/document-checklist/derive-from-1040",
             json=payload)
    return r.status_code in (200, 201)

def ledger_entry(client_id, client_name, doc_type, tax_year,
                 status="VALIDATED", stage="Filing", confidence=0.97):
    return {
        "client_id":        client_id,
        "client_name":      client_name,
        "document_type":    doc_type,
        "provider":         "NuExtract PRO",
        "description":      f"{doc_type} – TY{tax_year}",
        "source":           "seed",
        "tax_year":         tax_year,
        "stage":            stage,
        "status":           status,
        "cpa":              "demo@taxscio.ai",
        "confidence_score": confidence,
    }

def client_exists(first, last=None, biz=None, trust=None):
    """Return existing client_id if name already in DB, else None."""
    r = _req("get", "/clients?limit=500")
    if not r.ok:
        return None
    for c in r.json():
        if c.get("entity_type", "").upper() == "INDIVIDUAL":
            name = f"{c.get('first_name','')} {c.get('last_name','')}".strip()
            if first and last and name.lower() == f"{first} {last}".lower():
                return c["id"]
        elif biz and (c.get("business_name") or "").lower() == biz.lower():
            return c["id"]
        elif trust and (c.get("trust_name") or "").lower() == trust.lower():
            return c["id"]
    return None

# ═════════════════════════════════════════════════════════════════════════════
# CLIENT DEFINITIONS
# Each entry:
#   payload        → POST /clients body
#   form_1040      → extracted 1040 fields for TY2025
#   fc_1040        → field confidence map for the 1040
#   py_docs        → (form, count, confidence) prior-year TY2025 supporting docs
#   cy_submitted   → (form, status) current-year TY2026 docs already received
# ═════════════════════════════════════════════════════════════════════════════
CLIENTS = [

    # ── 1. JOHN & MARY HARTWELL ─ W-2 earners, homeowners, investments ────────
    {
        "payload": {
            "entity_type":     "INDIVIDUAL",
            "first_name":      "John",
            "last_name":       "Hartwell",
            "email":           "john.hartwell@email.com",
            "phone":           "555-101-2233",
            "tax_id":          "***-**-1101",
            "date_of_birth":   "1978-04-15",
            "lifecycle_stage": "ACTIVE",
            "risk_profile":    "LOW",
            "address_line1":   "42 Maple Drive",
            "city":            "Springfield",
            "state":           "IL",
            "zip_code":        "62701",
            "notes":           "MFJ – two W-2 earners, mortgage, brokerage account.",
        },
        "form_1040": {
            "tax_year":                     2025,
            "filing_status":                "Married Filing Jointly",
            "taxpayer_name":                "John Hartwell",
            "taxpayer_ssn":                 "***-**-1101",
            "spouse_name":                  "Mary Hartwell",
            "spouse_ssn":                   "***-**-1102",
            "wages_salaries_tips":          112500,
            "taxable_interest":             1840,
            "ordinary_dividends":           3220,
            "qualified_dividends":          2800,
            "capital_gain_or_loss":         4100,
            "schedule_d_required":          True,
            "ira_distributions":            0,
            "pensions_annuities":           0,
            "social_security_benefits":     0,
            "other_income":                 0,
            "total_income":                 121660,
            "student_loan_interest":        0,
            "agi":                          121660,
            "itemized_deductions":          28400,
            "mortgage_interest_paid":       14200,
            "charitable_contributions":     3800,
            "taxable_income":               93260,
            "child_tax_credit":             4000,
            "premium_tax_credit":           0,
            "total_tax":                    14820,
            "federal_income_tax_withheld":  16200,
            "refund_or_amount_owed":        -1380,
        },
        "fc_1040": {
            "wages_salaries_tips": 0.98, "taxable_interest": 0.96,
            "ordinary_dividends": 0.95, "capital_gain_or_loss": 0.93,
            "mortgage_interest_paid": 0.97, "itemized_deductions": 0.95,
        },
        "py_docs": [
            ("W-2",       2, 0.98),
            ("1099-INT",  1, 0.96),
            ("1099-DIV",  1, 0.95),
            ("1098",      1, 0.97),
            ("8949",      1, 0.92),
            ("Schedule D", 1, 0.91),
        ],
        "cy_submitted": [
            ("W-2",      "RECEIVED"),
            ("1099-DIV", "RECEIVED"),
        ],
    },

    # ── 2. KEVIN TORRES ─ Self-employed contractor, rental property ───────────
    {
        "payload": {
            "entity_type":     "INDIVIDUAL",
            "first_name":      "Kevin",
            "last_name":       "Torres",
            "email":           "kevin.torres@freelance.com",
            "phone":           "555-203-4455",
            "tax_id":          "***-**-2201",
            "date_of_birth":   "1985-09-22",
            "lifecycle_stage": "ACTIVE",
            "risk_profile":    "MEDIUM",
            "address_line1":   "19 Oak Street",
            "city":            "Austin",
            "state":           "TX",
            "zip_code":        "78701",
            "notes":           "Self-employed IT contractor. One rental property (Schedule E). Quarterly estimates.",
        },
        "form_1040": {
            "tax_year":                     2025,
            "filing_status":                "Single",
            "taxpayer_name":                "Kevin Torres",
            "taxpayer_ssn":                 "***-**-2201",
            "wages_salaries_tips":          0,
            "taxable_interest":             410,
            "ordinary_dividends":           0,
            "business_income_or_loss":      87300,
            "schedule_c_required":          True,
            "rental_real_estate_income":    18600,
            "schedule_e_required":          True,
            "capital_gain_or_loss":         0,
            "other_income":                 2100,
            "total_income":                 108410,
            "self_employment_tax":          12319,
            "deductible_part_of_se_tax":    6160,
            "agi":                          102250,
            "standard_deduction":           15000,
            "taxable_income":               87250,
            "total_tax":                    19870,
            "federal_income_tax_withheld":  0,
            "estimated_tax_payments":       18000,
            "refund_or_amount_owed":        1870,
        },
        "fc_1040": {
            "business_income_or_loss": 0.94, "rental_real_estate_income": 0.92,
            "self_employment_tax": 0.95, "estimated_tax_payments": 0.97,
        },
        "py_docs": [
            ("1099-NEC",     2, 0.95),
            ("1099-MISC",    1, 0.91),
            ("1099-INT",     1, 0.93),
            ("Schedule C",   1, 0.89),
            ("Schedule E",   1, 0.88),
            ("1040-ES",      4, 0.96),
        ],
        "cy_submitted": [
            ("1099-NEC", "RECEIVED"),
        ],
    },

    # ── 3. LINDA ZHAO ─ Retired, Social Security + pension + RMD ─────────────
    {
        "payload": {
            "entity_type":     "INDIVIDUAL",
            "first_name":      "Linda",
            "last_name":       "Zhao",
            "email":           "linda.zhao@retired.net",
            "phone":           "555-305-6677",
            "tax_id":          "***-**-3301",
            "date_of_birth":   "1952-02-08",
            "lifecycle_stage": "ACTIVE",
            "risk_profile":    "LOW",
            "address_line1":   "88 Willow Court",
            "city":            "Phoenix",
            "state":           "AZ",
            "zip_code":        "85001",
            "notes":           "Retired. SSA-1099 + pension (1099-R) + RMD from traditional IRA. No W-2.",
        },
        "form_1040": {
            "tax_year":                     2025,
            "filing_status":                "Single",
            "taxpayer_name":                "Linda Zhao",
            "taxpayer_ssn":                 "***-**-3301",
            "wages_salaries_tips":          0,
            "taxable_interest":             920,
            "ordinary_dividends":           1440,
            "qualified_dividends":          1440,
            "ira_distributions":            22000,
            "pensions_annuities":           18500,
            "social_security_benefits":     24000,
            "taxable_social_security":      20400,
            "capital_gain_or_loss":         0,
            "total_income":                 63260,
            "agi":                          63260,
            "standard_deduction":           16550,
            "taxable_income":               46710,
            "total_tax":                    5440,
            "federal_income_tax_withheld":  5800,
            "refund_or_amount_owed":        -360,
        },
        "fc_1040": {
            "ira_distributions": 0.96, "pensions_annuities": 0.95,
            "social_security_benefits": 0.97, "taxable_social_security": 0.94,
        },
        "py_docs": [
            ("SSA-1099",  1, 0.97),
            ("1099-R",    2, 0.96),
            ("1099-INT",  1, 0.93),
            ("1099-DIV",  1, 0.94),
        ],
        "cy_submitted": [],
    },

    # ── 4. MARCUS WILLIAMS ─ Young professional, ACA coverage, student loans ──
    {
        "payload": {
            "entity_type":     "INDIVIDUAL",
            "first_name":      "Marcus",
            "last_name":       "Williams",
            "email":           "marcus.williams@techcorp.io",
            "phone":           "555-407-8899",
            "tax_id":          "***-**-4401",
            "date_of_birth":   "1996-07-30",
            "lifecycle_stage": "ACTIVE",
            "risk_profile":    "LOW",
            "address_line1":   "305 Pine Avenue Apt 4B",
            "city":            "Seattle",
            "state":           "WA",
            "zip_code":        "98101",
            "notes":           "Software engineer. ACA marketplace coverage (1095-A/8962). Student loan interest deduction.",
        },
        "form_1040": {
            "tax_year":                     2025,
            "filing_status":                "Single",
            "taxpayer_name":                "Marcus Williams",
            "taxpayer_ssn":                 "***-**-4401",
            "wages_salaries_tips":          78400,
            "taxable_interest":             220,
            "ordinary_dividends":           0,
            "capital_gain_or_loss":         0,
            "total_income":                 78620,
            "student_loan_interest":        2500,
            "agi":                          76120,
            "standard_deduction":           15000,
            "taxable_income":               61120,
            "premium_tax_credit":           1200,
            "health_coverage_tax_credit":   1200,
            "form_8962_required":           True,
            "form_1095_a_required":         True,
            "total_tax":                    10082,
            "federal_income_tax_withheld":  9800,
            "refund_or_amount_owed":        918,
        },
        "fc_1040": {
            "wages_salaries_tips": 0.98, "student_loan_interest": 0.95,
            "premium_tax_credit": 0.91, "health_coverage_tax_credit": 0.90,
        },
        "py_docs": [
            ("W-2",      1, 0.98),
            ("1095-A",   1, 0.93),
            ("8962",     1, 0.91),
            ("1098-E",   1, 0.94),
        ],
        "cy_submitted": [
            ("W-2",    "RECEIVED"),
            ("1095-A", "RECEIVED"),
        ],
    },

    # ── 5. PATEL FAMILY TRUST ─ Investment trust, K-1s, dividend income ───────
    {
        "payload": {
            "entity_type":              "TRUST",
            "trust_name":               "Patel Family Trust",
            "email":                    "trustee@patelfamilytrust.com",
            "phone":                    "555-509-1122",
            "tax_id":                   "**-***6612",
            "date_of_incorporation":    "2015-03-10",
            "lifecycle_stage":          "ACTIVE",
            "risk_profile":             "MEDIUM",
            "address_line1":            "777 Lakeview Blvd",
            "city":                     "Chicago",
            "state":                    "IL",
            "zip_code":                 "60601",
            "notes":                    "Revocable living trust. Receives K-1 from two partnerships and a S-Corp. High dividend portfolio.",
        },
        "form_1040": {
            "tax_year":                     2025,
            "filing_status":                "Trust / Estate",
            "taxpayer_name":                "Patel Family Trust",
            "taxpayer_ssn":                 "**-***6612",
            "wages_salaries_tips":          0,
            "taxable_interest":             8200,
            "ordinary_dividends":           34500,
            "qualified_dividends":          31000,
            "capital_gain_or_loss":         12800,
            "schedule_d_required":          True,
            "partnership_s_corp_income":    55000,
            "schedule_e_required":          True,
            "total_income":                 110500,
            "agi":                          110500,
            "taxable_income":               86500,
            "total_tax":                    23410,
            "federal_income_tax_withheld":  22000,
            "estimated_tax_payments":       5000,
            "refund_or_amount_owed":        3590,
        },
        "fc_1040": {
            "taxable_interest": 0.95, "ordinary_dividends": 0.97,
            "capital_gain_or_loss": 0.93, "partnership_s_corp_income": 0.89,
        },
        "py_docs": [
            ("1099-INT",   2, 0.96),
            ("1099-DIV",   3, 0.97),
            ("K-1 (1065)", 2, 0.88),
            ("K-1 (1120S)",1, 0.86),
            ("8949",       1, 0.91),
            ("Schedule D", 1, 0.90),
        ],
        "cy_submitted": [
            ("1099-INT", "RECEIVED"),
            ("1099-DIV", "RECEIVED"),
        ],
    },
]

# ═════════════════════════════════════════════════════════════════════════════
# SEED LOOP
# ═════════════════════════════════════════════════════════════════════════════
TY_PRIOR   = 2025
TY_CURRENT = 2026
created = 0

for c in CLIENTS:
    entity   = c["payload"]["entity_type"]
    py_docs  = c["py_docs"]
    cy_sub   = c["cy_submitted"]

    # Display name
    if entity == "INDIVIDUAL":
        display = f"{c['payload']['first_name']} {c['payload']['last_name']}"
        exists_id = client_exists(c["payload"]["first_name"], c["payload"]["last_name"])
    elif entity == "BUSINESS":
        display = c["payload"]["business_name"]
        exists_id = client_exists(None, biz=display)
    else:
        display = c["payload"]["trust_name"]
        exists_id = client_exists(None, trust=display)

    print(f"\n{'─'*60}")
    print(f"→ {display}")

    if exists_id:
        print(f"  ⚠  Already exists (id={exists_id}) — skipping client creation.")
        client_id = exists_id
    else:
        # 1. Create client ─────────────────────────────────────────────────────
        result = post("/clients", c["payload"])
        if not result:
            print("  Skipping — client creation failed.")
            continue
        client_id = result["id"]
        print(f"  ✓ Created  client_id={client_id}")

    # 2. Submit TY2025 1040 to ledger ──────────────────────────────────────────
    print(f"  Submitting TY{TY_PRIOR} 1040 to ledger…")
    ok = ledger_submit(ledger_entry(
        client_id, display, "1040", TY_PRIOR,
        status="VALIDATED", stage="Filing", confidence=0.97,
    ))
    print(f"    {'✓ 1040 ledger' if ok else '✗ 1040 ledger failed'}")

    # 3. Save 1040 JSON snapshot to local_extraction/ ─────────────────────────
    print(f"  Saving 1040 JSON snapshot…")
    snap_key = f"seed_1040_{display.replace(' ', '_')}_TY{TY_PRIOR}"
    ok = save_snapshot(
        doc_id             = snap_key,
        form_type          = "1040",
        filename           = f"{display.replace(' ', '_')}_1040_{TY_PRIOR}.pdf",
        pdf_type           = "digital",
        data               = c["form_1040"],
        exceptions         = [],
        document_confidence= 0.97,
        field_confidence   = c["fc_1040"],
    )
    print(f"    {'✓ snapshot saved' if ok else '✗ snapshot failed'}")

    # 4. Derive document checklist from 1040 ───────────────────────────────────
    print(f"  Deriving document checklist (FDR)…")
    ok = derive_checklist(
        client_id      = client_id,
        tax_year       = TY_PRIOR,
        extracted_fields = c["form_1040"],
        field_confidence = c["fc_1040"],
    )
    print(f"    {'✓ checklist derived' if ok else '✗ FDR failed (non-fatal)'}")

    # 5. Prior-year supporting docs (TY2025 ledger) ────────────────────────────
    print(f"  Seeding TY{TY_PRIOR} supporting docs ({len(py_docs)} types)…")
    for doc_type, count, conf in py_docs:
        for i in range(count):
            ok = ledger_submit(ledger_entry(
                client_id, display, doc_type, TY_PRIOR,
                status="VALIDATED", stage="Filing", confidence=conf,
            ))
            print(f"    {'✓' if ok else '✗'} {doc_type} #{i+1}")

    # 6. Current-year submitted docs (TY2026 ledger) ───────────────────────────
    if cy_sub:
        print(f"  Seeding TY{TY_CURRENT} received docs ({len(cy_sub)})…")
        for doc_type, status in cy_sub:
            ok = ledger_submit(ledger_entry(
                client_id, display, doc_type, TY_CURRENT,
                status=status, stage="Document Submission", confidence=0.96,
            ))
            print(f"    {'✓' if ok else '✗'} {doc_type} ({status})")

    created += 1
    time.sleep(0.2)

print(f"\n{'═'*60}")
print(f"✅  Done — {created}/{len(CLIENTS)} clients seeded.")
print("   Refresh your browser to see the new data.")
print(f"{'═'*60}")
