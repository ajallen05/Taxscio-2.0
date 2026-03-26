# Taxscio Filing Pipeline - Setup & Usage Guide

Complete guide to set up and run the Taxscio filing pipeline with sample data.

---

## 📋 Table of Contents

1. [Quick Start (5 minutes)](#quick-start)
2. [Prerequisites](#prerequisites)
3. [Database Setup](#database-setup)
4. [Running the Application](#running-the-application)
5. [Generating Sample Pipeline Data](#generating-sample-data)
6. [Filing Pipeline Features](#filing-pipeline-features)
7. [Troubleshooting](#troubleshooting)

---

## 🚀 Quick Start

If you already have databases set up, just run:

```bash
# Generate sample filing pipeline data from existing clients
python generate_pipeline_from_clients.py

# Start the backend
cd backend
python main.py

# In another terminal, start the frontend
cd frontend
npm run dev
```

Then open your browser to `http://localhost:5173` and navigate to **Filing Pipeline**.

---

## ✅ Prerequisites

- **Python 3.8+**
- **PostgreSQL 12+** running locally
- **Node.js 16+** and npm
- **Database Credentials:** Default is `postgresql://postgres:0406@localhost:5432/`

### Create Databases

If you haven't created the databases yet:

```bash
python create_db.py
```

This creates:
- `client_database` — Client profiles, enums, and metadata
- `ledgerdb` — Document ledger, pipeline stages, and confidence scores

---

## 🗄️ Database Setup

### Step 1: Verify Database Connection

```bash
# Test connection (you'll see your PostgreSQL version)
psql -U postgres -h localhost -d postgres -c "SELECT version();"
```

### Step 2: Create Databases

```bash
# From project root
python create_db.py
```

Expected output:
```
Created client_database
Created ledgerdb
```

### Step 3: Seed Enums and Base Tables

Using Docker Compose:
```bash
docker-compose up -d
```

Or manually initialize with SQL scripts:
```bash
psql -U postgres -d client_database -f backend/client_database/seed_client_database.sql
```

---

## 🚀 Running the Application

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
python main.py
```

Backend runs on `http://localhost:8000`

API endpoint for testing: `http://localhost:8000/docs` (Swagger UI)

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`

---

## 📊 Generating Sample Pipeline Data

The FilingPipeline view requires sample data in the **ledger database**.

### Option A: Generate from Existing Clients (Recommended)

```bash
# From project root
python generate_pipeline_from_clients.py
```

This script:
- Reads all clients from `client_database`
- Creates 2-4 documents per client with:
  - Random document types (W-2, 1040, 1099-INT, etc.)
  - Random pipeline stages (Document Collection → Filed & Confirmed)
  - Random confidence scores (65-98%)
  - Realistic due dates

**Output:** 30+ documents ready for viewing

### Option B: Manual Data Entry

Use the **Ingestion Hub** page in the UI to upload PDFs/forms, which automatically creates ledger entries.

---

## 📁 Filing Pipeline Features

### Parent Row (Client Level)
- **CLIENT:** Client name
- **# FORMS:** Number of documents
- **STAGE:** Client's lifecycle stage (ACTIVE, PROSPECT, DORMANT, CLOSED)
- **CONFIDENCE:** — (empty by design)
- **STATUS:** — (empty by design)

### Child Rows (Document Level)
When you click to expand a client:
- **FORM:** Document type (W-2, 1040, etc.)
- **VERSION / UPLOADS:** e.g., "2 / 2" (version 2, uploaded 2 times)
- **STAGE:** Current pipeline stage
- **CONFIDENCE:** Confidence score with color coding:
  - 🟢 **Green:** 90%+ confidence
  - 🟡 **Amber:** 75-89% confidence
  - 🔴 **Red:** <75% confidence
- **STATUS:** Processing / Complete / Exception

### Pipeline Stages

1. **Document Collection** — Initial upload
2. **AI Processing** — OCR extraction & analysis
3. **Exception Review** — Manual review of discrepancies
4. **CPA Review** — Accountant review
5. **Client Approval** — Client signs off
6. **Ready to E-File** — Final review before filing
7. **Filed & Confirmed** — Submitted to IRS

---

## Configuration

### Environment Variables

`.env` file in `backend/` directory:

```env
DATABASE_URL=postgresql://postgres:0406@localhost:5432/ledgerdb
CLIENT_DATABASE_URL=postgresql://postgres:0406@localhost:5432/client_database
```

### Database Credentials

- **Host:** localhost
- **Port:** 5432
- **User:** postgres
- **Password:** 0406

---

## 🔧 Common Tasks

### Add More Sample Data

Re-run the generator:
```bash
python generate_pipeline_from_clients.py
```

Each run creates new documents with random stages and confidence scores.

### Clear All Pipeline Data

```bash
psql -U postgres -d ledgerdb -c "DELETE FROM ledger;"
```

Then regenerate with:
```bash
python generate_pipeline_from_clients.py
```

### Update Client Lifecycle Stage

```bash
psql -U postgres -d client_database -c "
  UPDATE clients SET lifecycle_stage = 'ACTIVE' WHERE lifecycle_stage IS NULL;
"
```

Valid stages: `ACTIVE`, `PROSPECT`, `DORMANT`, `CLOSED`

### View Database Schema

```bash
# Client database
psql -U postgres -d client_database -c "
  \dt
"

# Ledger database
psql -U postgres -d ledgerdb -c "
  SELECT table_name FROM information_schema.tables WHERE table_schema='public';
"
```

---

## 📈 Using the Filing Pipeline

### View Pipeline

1. Open `http://localhost:5173`
2. Go to **Filing Pipeline** page
3. Select **Table** view (default)

### Expand Client Details

1. Click the **▶ arrow** next to a client name
2. Children rows appear showing all documents for that client
3. Each row shows:
   - Document type
   - Pipeline stage
   - Confidence score
   - Upload count

### Filter by Document Type

Use the filter chips at the top:
- All Types, 1040, 1120, 1065, W-2, 1099, etc.

### Switch to Kanban View

Click **Board** button to see pipeline as a Kanban board (document-level grouping).

---

## 🐛 Troubleshooting

### "No documents yet"

**Problem:** Filing Pipeline shows empty table.

**Solution:**
```bash
# Verify ledger has data
psql -U postgres -d ledgerdb -c "SELECT COUNT(*) FROM ledger;"

# If 0, generate sample data
python generate_pipeline_from_clients.py
```

### Lifecycle Stage Shows "—"

**Problem:** Parent row shows "—" for stage instead of "ACTIVE".

**Solution:**
1. Verify client exists in `client_database`:
   ```bash
   psql -U postgres -d client_database -c "SELECT business_name, lifecycle_stage FROM clients LIMIT 5;"
   ```
2. Ensure stage is set to official enum (uppercase):
   ```bash
   psql -U postgres -d client_database -c "
     UPDATE clients SET lifecycle_stage = 'ACTIVE' WHERE lifecycle_stage IS NULL;
   "
   ```
3. Refresh browser

### API Returns 422 Error

**Problem:** `/clients` endpoint returns HTTP 422.

**Solution:**
The API has a max `limit` of 500. Frontend now uses `limit=500` (fixed).

If error persists, check:
```bash
# Verify endpoint works
curl "http://localhost:8000/clients?limit=100"
```

### Version / Upload Count Shows "1 / 1" but DB has "2 / 2"

**Problem:** Child rows don't show correct upload count.

**Solution:**
1. Restart backend server:
   ```bash
   # Kill existing process and restart
   cd backend && python main.py
   ```
2. Refresh browser (browser uses 10-second poll)

---

## 📝 File Structure

```
Taxscio-2.0-main/
├── backend/
│   ├── main.py                          # FastAPI app
│   ├── requirements.txt                 # Python dependencies
│   ├── client_database/
│   │   ├── models.py                   # Client ORM models
│   │   ├── routes.py                   # /clients endpoints
│   │   └── seed_client_database.sql    # Seed data
│   ├── ledger/
│   │   ├── models.py                   # Ledger ORM models
│   │   ├── routes.py                   # /ledger/ledger endpoints
│   │   └── database.py                 # DB connection
│   └── adapters/                       # OCR & extraction
├── frontend/
│   ├── src/
│   │   ├── App.jsx                     # Main app (Filing Pipeline view here)
│   │   └── ...
│   └── package.json
├── create_db.py                         # Initialize databases
├── generate_pipeline_from_clients.py    # Generate sample data ⭐
└── docker-compose.yml                   # PostgreSQL container (optional)
```

---

## 🎯 Next Steps

1. **Run the generator:** `python generate_pipeline_from_clients.py`
2. **Start backend:** `cd backend && python main.py`
3. **Start frontend:** `cd frontend && npm run dev`
4. **View pipeline:** `http://localhost:5173` → Filing Pipeline
5. **Explore features:**
   - Expand clients to see documents
   - View stages and confidence scores
   - Try different filters

---

## ✨ Features

- ✅ Real-time data from ledger API (10-second refresh)
- ✅ Multi-stage pipeline (7 stages)
- ✅ Confidence scoring with color coding
- ✅ Client lifecycle stage tracking
- ✅ Document version/upload history
- ✅ Table and Kanban views
- ✅ Filter by document type
- ✅ Expandable client details

---

## 📞 Support

For issues or questions:
1. Check **Troubleshooting** section above
2. Verify database connection: `psql -U postgres -h localhost`
3. Check backend logs for errors: `python -c "import main; main.app"`
4. Check browser console (F12) for frontend errors

---

## 📄 License

Taxscio - Tax Processing Platform

---

**Last Updated:** March 23, 2026
