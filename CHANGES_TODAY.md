# Taxscio 2.0 — Changes Made Today (27 Mar 2026)

This document describes every change made in today's development session and provides a complete guide for setting up the project on a new computer.

---

## Table of Contents

1. [What Was Changed Today](#1-what-was-changed-today)
2. [New Files Created](#2-new-files-created)
3. [Setting Up on a New Computer](#3-setting-up-on-a-new-computer)
4. [Adding New Clients / Data](#4-adding-new-clients--data)
5. [Environment Variables Reference](#5-environment-variables-reference)

---

## 1. What Was Changed Today

### A. Linked the Client Database and Ledger Database by `client_id`

**Problem:** The two PostgreSQL databases (client database and ledger) were connected only by `client_name` (a plain text string). This was fragile — if a name had a typo or changed, records would become orphaned.

**Fix:** Added a `client_id` UUID column to the ledger tables so every ledger entry can reference the exact client record.

Files changed:
- `backend/ledger/models.py` — added `client_id` and `extraction_json_path` columns to `Ledger` and `DocumentLog` models.
- `backend/ledger/schemas.py` — added `client_id` and `extraction_json_path` fields to `DocumentCreate` schema.
- `backend/ledger/services.py` — writes `client_id` when creating/updating ledger entries.
- `backend/ledger/database.py` — added automatic `ALTER TABLE … ADD COLUMN IF NOT EXISTS` migrations that run on startup (safe to run multiple times).
- `backend/ledger/routes.py` — added new `PATCH /ledger/associate-client` endpoint to backfill `client_id` on older records.
- `backend/client_database/services.py` — `get_client_document_checklist` now queries ledger by `client_id` first, falling back to `client_name` for old records.

---

### B. Fixed "Add Client" Modal — Save Button Was Missing

**Problem:** When uploading a document that didn't match any existing client, a modal appeared to create a new client. But the form had no Save button, so you could fill it in but never actually save.

**Fix:** Added "← Back" and "Save Client" buttons to the `ClientMatchModal` inside `App.tsx`, correctly wired to the `AddClientForm` submit handler.

Files changed:
- `frontend/src/App.tsx`
- `frontend/src/AddClientForm.tsx`

---

### C. Made `lifecycle_stage` a Required Field

**Problem:** The "Lifecycle Stage" field in the Add Client form was optional, but it is needed for proper workflow routing.

**Fix:** Added front-end validation that blocks submission if `lifecycle_stage` is empty, and displays a required `*` indicator on the field label.

Files changed:
- `frontend/src/AddClientForm.tsx`

---

### D. Automatic Local JSON Saving

**Problem:** Extracted JSON data was only stored inside the database as a raw blob. There was no human-readable local copy, and changes (field edits, exception resolutions) were not reflected anywhere on disk.

**Fix:**
- Created `backend/local_extraction_store.py` — a utility module that saves, reads, and updates JSON files in `backend/local_extraction/`.
- Every extraction, validation, field edit, and exception resolution now automatically writes/updates the corresponding JSON file.
- No button click is required — saving is fully automatic.
- File naming convention: `DOC-<id>.json` for real uploads, `seed_1040_<name>_TY<year>.json` for seeded data.

Files changed / created:
- `backend/local_extraction_store.py` *(new)*
- `backend/local_extraction/` folder *(new — auto-created at runtime)*
- `backend/main.py` — added `POST /save-snapshot` endpoint; hooked `/extract`, `/validate`, `/apply-fixes`, and `/revalidate` to save after processing.

---

### E. Ledger Stores Only the JSON File Path (Not the Blob)

**Problem:** The ledger was storing the full extracted JSON as a database column, which made the database heavy and hard to inspect.

**Fix:** The ledger now stores only the relative path `local_extraction/<doc_id>.json`. The actual data lives in the file.

Files changed:
- `backend/ledger/models.py` (`extraction_json_path` column)
- `backend/main.py` (patches `extraction_json_path` on the ledger entry after saving)

---

### F. Exception Resolution Updates the Local JSON

**Problem:** When you clicked "Complete" on an exception in the Ingestion Hub, the UI updated, but the local JSON file kept the exception in its `exceptions` array.

**Fix:** Added `mark_exception_resolved()` in `local_extraction_store.py`. This function atomically:
1. Removes the exception from the `exceptions` array.
2. Appends an audit entry to `exception_audit`.

The `PATCH /ledger/escalate-exception` route now calls this function every time an exception is resolved.

---

### G. Backend Always Re-Validates Before Saving

**Problem:** The `POST /save-snapshot` endpoint was a "dumb passthrough" — it trusted whatever `exceptions` and `confidence` values the frontend sent, even if they were stale or empty.

**Fix:** `save_snapshot_route` in `backend/main.py` now always runs the backend's `_data_integrity.validate()` engine before saving. The `exceptions` and `document_confidence` written to disk are always computed by the backend, never blindly copied from the caller.

---

### H. Removed Stale `extract_` Prefixed JSON Files

**Problem:** Early in a document's lifecycle, a temporary file named `extract_<something>.json` was created with incomplete data (confidence = 1.0, no exceptions). This file was never updated, confusing anyone who opened it.

**Fix:** Removed the early-save block from the `/extract` endpoint for `fields_only=true` calls. Stale `extract_` files were deleted from `backend/local_extraction/`.

---

### I. Sample Data Seeding Scripts

Two seeding scripts were created to populate the system with realistic data for testing:

- `backend/seed_sample_data.py` — seeds basic clients and ledger entries.
- `backend/seed_1040_clients.py` — seeds 5 detailed 1040 client profiles with full extraction JSONs, checklists, and multi-year ledger entries.

Client profiles included:
| Name | Scenario |
|------|----------|
| John Hartwell | W-2 employee with mortgage |
| Kevin Torres | Self-employed (Schedule C) |
| Linda Zhao | Retired with pension/RMD |
| Marcus Williams | ACA marketplace coverage |
| Patel Family Trust | Trust return with K-1s |

---

## 2. New Files Created

| File | Purpose |
|------|---------|
| `backend/local_extraction_store.py` | Utility for saving/reading/updating local extraction JSON files |
| `backend/local_extraction/` | Folder where all extraction JSON files are stored |
| `backend/seed_sample_data.py` | Seeds basic clients and ledger entries |
| `backend/seed_1040_clients.py` | Seeds 5 realistic 1040 client profiles |
| `backend/fdr/` | Form Dependency Resolver engine (rule-based checklist derivation) |
| `backend/rules/` | Business rules used by the FDR and data integrity engines |

---

## 3. Setting Up on a New Computer

Follow these steps exactly, in order.

### Prerequisites

Install these before starting:

- **Python 3.11** — https://www.python.org/downloads/
- **Node.js 18+** — https://nodejs.org/
- **PostgreSQL 15+** — https://www.postgresql.org/download/
- **Git** — https://git-scm.com/

---

### Step 1 — Clone the Repository

```bash
git clone <your-repo-url> Taxscio-2.0
cd Taxscio-2.0
```

---

### Step 2 — Create the Two PostgreSQL Databases

Open `psql` and run:

```sql
CREATE DATABASE taxscio_clients;
CREATE DATABASE taxscio_ledger;
```

If you want a dedicated user:

```sql
CREATE USER taxscio WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE taxscio_clients TO taxscio;
GRANT ALL PRIVILEGES ON DATABASE taxscio_ledger TO taxscio;
```

---

### Step 3 — Configure Environment Variables

Create a file called `.env` inside the `backend/` folder:

```
backend/.env
```

Paste in the following and fill in your values:

```env
# ── Client Database ────────────────────────────────────────────────
CLIENT_DB_URL=postgresql://taxscio:yourpassword@localhost:5432/taxscio_clients

# ── Ledger Database ────────────────────────────────────────────────
LEDGER_DB_URL=postgresql://taxscio:yourpassword@localhost:5432/taxscio_ledger

# ── OpenAI (for PDF extraction) ───────────────────────────────────
OPENAI_API_KEY=sk-...

# ── Optional ──────────────────────────────────────────────────────
# LOG_LEVEL=DEBUG
```

> **Note:** The database tables and migrations run automatically when the backend starts. You do NOT need to run any SQL migration scripts manually.

---

### Step 4 — Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

If you only need the core features (no OCR for scanned PDFs), you can skip the PaddleOCR packages — comment out the `paddlepaddle` and `paddleocr` lines in `requirements.txt` first.

---

### Step 5 — Install Frontend Dependencies

```bash
cd frontend
npm install
```

---

### Step 6 — Start the Backend

From the `backend/` folder:

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The backend also starts a Flask ledger server automatically on port **5050** via a subprocess inside `main.py`.

You should see log output confirming:
- Tables created
- Migrations applied (`client_id`, `extraction_json_path` columns)
- Both FastAPI and Flask running

---

### Step 7 — Start the Frontend

In a separate terminal, from the `frontend/` folder:

```bash
cd frontend
npm run dev
```

Open your browser at **http://localhost:5173**

---

### Step 8 — Seed Sample Data (Optional but Recommended)

Once both servers are running, seed realistic client data:

```bash
cd backend
python seed_1040_clients.py
```

This creates 5 clients with full 1040 extraction JSONs, checklists, and prior-year ledger entries. It is safe to run multiple times — it skips clients that already exist.

For basic sample data (simpler, more documents):

```bash
cd backend
python seed_sample_data.py
```

---

## 4. Adding New Clients / Data

### Adding a Client via the UI

1. Open the app at http://localhost:5173.
2. Go to the **Client Database** tab.
3. Click **+ Add Client**.
4. Fill in all fields. **Lifecycle Stage is required.**
5. Click **Save**.

### Adding a Client via API

```bash
curl -X POST http://localhost:8000/clients \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Smith",
    "email": "jane@example.com",
    "phone": "555-1234",
    "lifecycle_stage": "Onboarding",
    "entity_type": "Individual"
  }'
```

### Uploading a Document (Ingestion Hub)

1. Go to the **Ingestion Hub** tab.
2. Click **Upload PDF**.
3. Select a tax document (W-2, 1099, 1040, etc.).
4. The system will:
   - Extract fields using AI.
   - Validate and flag exceptions.
   - Automatically save a JSON file to `backend/local_extraction/DOC-<id>.json`.
   - Ask you to match or create a client.
5. After matching, click **Submit to Ledger**.

### Resolving Exceptions

1. In the Ingestion Hub, after uploading, open the **Exceptions** tab.
2. Click **Complete** next to any exception.
3. The local JSON file is automatically updated — the exception is moved from `exceptions` to `exception_audit`.

### Adding New 1040 Seed Data Manually

Edit `backend/seed_1040_clients.py` and add a new entry to the `CLIENTS` list:

```python
{
    "name": "Your Client Name",
    "email": "client@example.com",
    "phone": "555-0000",
    "lifecycle_stage": "Filing",
    "entity_type": "Individual",
    "1040": {
        "filing_status": "Single",
        "wages": 75000,
        # ... add fields matching the 1040 schema
    }
}
```

Then re-run:

```bash
python seed_1040_clients.py
```

---

## 5. Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `CLIENT_DB_URL` | Yes | PostgreSQL connection string for the client database |
| `LEDGER_DB_URL` | Yes | PostgreSQL connection string for the ledger database |
| `OPENAI_API_KEY` | Yes | OpenAI API key for PDF field extraction |
| `LOG_LEVEL` | No | Python logging level (`DEBUG`, `INFO`, `WARNING`). Default: `INFO` |

---

## Architecture Overview

```
frontend/          React + Vite (port 5173)
    src/App.tsx        Main UI, all tabs, ingestion hub
    src/AddClientForm  Add client form component

backend/           Python
    main.py            FastAPI server (port 8000)
                       - POST /extract
                       - POST /validate
                       - POST /apply-fixes
                       - POST /revalidate
                       - POST /save-snapshot   ← saves local JSON
                       - GET/POST /clients/...

    ledger/            Flask blueprint (port 5050, started by main.py)
                       - POST /ledger/submit
                       - PATCH /ledger/escalate-exception
                       - PATCH /ledger/associate-client

    client_database/   SQLAlchemy models + services for client DB
    local_extraction/  Auto-created folder — one JSON file per document
    local_extraction_store.py   Utility for reading/writing those files
    fdr/               Form Dependency Resolver — derives checklists
    rules/             Business rules for validation and FDR
    seed_1040_clients.py        Seed 5 realistic 1040 profiles
    seed_sample_data.py         Seed basic sample clients
```

---

*Last updated: 27 Mar 2026*
