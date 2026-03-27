"""
seed_sample_data.py
Inserts realistic sample clients, prior-year (TY2025) ledger entries,
and current-year (TY2026) checklist state for testing the Document Checklist tab.

Run from the backend directory:
    python seed_sample_data.py
"""
import uuid, requests, time

BASE = "http://127.0.0.1:8000"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def post(path, payload):
    r = requests.post(f"{BASE}{path}", json=payload, timeout=10)
    if r.status_code not in (200, 201):
        print(f"  ✗ {path} → {r.status_code}: {r.text[:120]}")
        return None
    return r.json()

def ledger_entry(client_name, doc_type, tax_year, status="VALIDATED",
                 stage="Filing", upload_count=1, confidence=0.97, client_id=None):
    entry = {
        "client_name":      client_name,
        "document_type":    doc_type,
        "provider":         "NuExtract PRO",
        "description":      f"{doc_type} – TY{tax_year}",
        "source":           "upload",
        "tax_year":         tax_year,
        "stage":            stage,
        "status":           status,
        "cpa":              "demo@taxscio.ai",
        "confidence_score": confidence,
    }
    if client_id:
        entry["client_id"] = client_id
    return entry

# ─────────────────────────────────────────────────────────────────────────────
# 1. CLIENT DEFINITIONS
#    Each entry: API payload + prior-year (TY2025) ledger docs
# ─────────────────────────────────────────────────────────────────────────────
CLIENTS = [
    {
        "payload": {
            "entity_type":   "INDIVIDUAL",
            "first_name":    "Sarah",
            "last_name":     "Mitchell",
            "email":         "sarah.mitchell@email.com",
            "phone":         "555-201-4433",
            "tax_id":        "***-**-1234",
            "lifecycle_stage": "ACTIVE",
        },
        "py_docs": [
            ("W-2",       2, 0.98),
            ("1099-INT",  1, 0.96),
            ("1099-DIV",  1, 0.95),
            ("1098",      1, 0.94),
            ("8949",      1, 0.91),
        ],
        "cy_submitted": [
            ("W-2", "RECEIVED"),
        ],
    },
    {
        "payload": {
            "entity_type":   "INDIVIDUAL",
            "first_name":    "Robert",
            "last_name":     "Chen",
            "email":         "robert.chen@email.com",
            "phone":         "555-308-7762",
            "tax_id":        "***-**-5678",
            "lifecycle_stage": "ACTIVE",
        },
        "py_docs": [
            ("W-2",      2, 0.98),
            ("1099-NEC", 1, 0.93),
            ("1099-INT", 1, 0.95),
            ("8949",     1, 0.89),
            ("1095-A",   1, 0.92),
            ("8962",     1, 0.90),
        ],
        "cy_submitted": [
            ("W-2",      "RECEIVED"),
            ("1099-NEC", "RECEIVED"),
        ],
    },
    {
        "payload": {
            "entity_type":   "INDIVIDUAL",
            "first_name":    "Maria",
            "last_name":     "Rodriguez",
            "email":         "maria.rodriguez@email.com",
            "phone":         "555-417-9901",
            "tax_id":        "***-**-3399",
            "lifecycle_stage": "ACTIVE",
        },
        "py_docs": [
            ("W-2",      1, 0.97),
            ("1099-R",   1, 0.94),
            ("SSA-1099", 1, 0.96),
            ("1099-INT", 1, 0.93),
            ("8812",     1, 0.90),
        ],
        "cy_submitted": [],
    },
    {
        "payload": {
            "entity_type":   "INDIVIDUAL",
            "first_name":    "David",
            "last_name":     "Thompson",
            "email":         "david.thompson@email.com",
            "phone":         "555-519-3340",
            "tax_id":        "***-**-7712",
            "lifecycle_stage": "ACTIVE",
        },
        "py_docs": [
            ("W-2",           3, 0.98),
            ("1099-INT",      2, 0.95),
            ("1099-DIV",      2, 0.94),
            ("K-1 (1065)",    1, 0.88),
            ("8863",          1, 0.91),
            ("1098-T",        1, 0.93),
        ],
        "cy_submitted": [
            ("W-2",       "RECEIVED"),
            ("1099-INT",  "RECEIVED"),
            ("1099-DIV",  "RECEIVED"),
        ],
    },
    {
        "payload": {
            "entity_type":   "BUSINESS",
            "business_name": "Summit Consulting LLC",
            "email":         "tax@summitconsulting.com",
            "phone":         "555-620-8843",
            "tax_id":        "**-***4521",
            "lifecycle_stage": "ACTIVE",
        },
        "py_docs": [
            ("W-2",       4, 0.97),
            ("1099-NEC",  3, 0.92),
            ("1099-MISC", 1, 0.89),
            ("1098",      1, 0.93),
            ("8949",      2, 0.88),
        ],
        "cy_submitted": [
            ("W-2",       "RECEIVED"),
            ("1099-NEC",  "RECEIVED"),
        ],
    },
    {
        "payload": {
            "entity_type":   "TRUST",
            "trust_name":    "Johnson Family Trust",
            "email":         "trustee@johnsonftrust.com",
            "phone":         "555-723-5521",
            "tax_id":        "**-***8834",
            "lifecycle_stage": "ACTIVE",
        },
        "py_docs": [
            ("1099-INT",    2, 0.96),
            ("1099-DIV",    3, 0.95),
            ("K-1 (1041)",  1, 0.87),
            ("K-1 (1065)",  1, 0.86),
            ("8949",        1, 0.90),
        ],
        "cy_submitted": [
            ("1099-INT",  "RECEIVED"),
            ("1099-DIV",  "RECEIVED"),
        ],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# 2. SEED
# ─────────────────────────────────────────────────────────────────────────────
created = 0

for c in CLIENTS:
    entity   = c["payload"]["entity_type"]
    py_docs  = c["py_docs"]
    cy_sub   = c["cy_submitted"]

    # Derive display name for ledger entries
    if entity == "INDIVIDUAL":
        display = f"{c['payload']['first_name']} {c['payload']['last_name']}"
    elif entity == "BUSINESS":
        display = c["payload"]["business_name"]
    else:
        display = c["payload"]["trust_name"]

    print(f"\n→ Creating client: {display}")

    # 2a. Create client
    result = post("/clients", c["payload"])
    if not result:
        print(f"  Skipping — client creation failed")
        continue
    client_id = result["id"]
    print(f"  ✓ Client ID: {client_id}")

    # 2b. Prior-year (TY2025) ledger entries
    print(f"  Seeding TY2025 ledger ({len(py_docs)} form types)…")
    for doc_type, upload_count, confidence in py_docs:
        for i in range(upload_count):
            entry = ledger_entry(display, doc_type, 2025,
                                 status="VALIDATED", stage="Filing",
                                 confidence=confidence, client_id=client_id)
            r = requests.post(f"{BASE}/ledger/submit", json=entry, timeout=10)
            if r.status_code != 200:
                print(f"    ✗ {doc_type} #{i+1}: {r.status_code}")
            else:
                print(f"    ✓ {doc_type} #{i+1}")

    # 2c. Current-year (TY2026) submitted docs in ledger
    if cy_sub:
        print(f"  Seeding TY2026 submitted docs ({len(cy_sub)})…")
        for doc_type, status in cy_sub:
            entry = ledger_entry(display, doc_type, 2026,
                                 status=status, stage="Document Submission",
                                 confidence=0.96, client_id=client_id)
            r = requests.post(f"{BASE}/ledger/submit", json=entry, timeout=10)
            if r.status_code != 200:
                print(f"    ✗ {doc_type}: {r.status_code}")
            else:
                print(f"    ✓ {doc_type} ({status})")

    # Small delay between clients
    time.sleep(0.3)
    created += 1

print(f"\n✅ Done — {created}/{len(CLIENTS)} clients seeded successfully.")
print("Refresh your browser to see the new data.")
