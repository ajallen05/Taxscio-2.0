# Taxscio Filling Pipeline - Quick Start Guide

## What is the Filling Pipeline?

The Taxscio filling pipeline is an automated system that:
1. **Extracts** data from tax documents (PDFs) using OCR
2. **Validates** the extracted data for accuracy
3. **Auto-fills** larger tax forms using extracted data from source documents
4. **Scores** the quality and confidence of filled data
5. **Reviews** forms before submitting to the IRS

## Getting Started in 5 Minutes

### Step 1: Verify Your Setup

```bash
# Check Python is installed
python --version

# Check PostgreSQL is running
psql -U postgres -c "SELECT version();"

# Navigate to project root
cd /path/to/Taxscio-2.0-main
```

### Step 2: Generate Sample Data

```bash
# This creates clients, enums, and sample form data in the database
python sample_pipeline_data.py
```

**Expected Output:**
```
======================================================================
Taxscio - Sample Pipeline Data Generator
======================================================================

Inserting enum values...
  ✓ Created enum: entity_type - individual
  ✓ Created enum: filing_status - single
  ...

Inserting sample clients...
  ✓ Created client: John Smith
  ✓ Created client: Jane Doe
  ✓ Created client: Tech Solutions LLC

Inserting ledger entries...
  ✓ Created ledger entry: doc-001-w2-2025
  ...

Creating sample form data files...
  ✓ Created: backend/sample_data/sample_w2_extraction.json
  ✓ Created: backend/sample_data/sample_1040_extraction.json
  ✓ Created: backend/sample_data/sample_1099int_extraction.json

======================================================================
✓ Sample data generation completed successfully!
======================================================================
```

### Step 3: Explore the Sample Data

```bash
# View the sample W-2 extraction
cat backend/sample_data/sample_w2_extraction.json | python -m json.tool

# View the auto-filled 1040 form
cat backend/sample_data/sample_1040_extraction.json | python -m json.tool

# Run the pipeline examples
python backend/sample_data/pipeline_examples.py
```

### Step 4: Start the API Server

```bash
cd backend
python main.py
```

The API will be available at: `http://localhost:8000`

### Step 5: Test the Pipeline

In a new terminal:

```bash
# Check server is running
curl http://localhost:8000/api/health

# View sample client data
curl http://localhost:8000/api/clients

# Validate a W-2 extraction
curl -X POST http://localhost:8000/api/validation/validate \
  -H "Content-Type: application/json" \
  -d @backend/sample_data/sample_w2_extraction.json
```

## Understanding the Sample Data

### Three Sample Clients

| Name | Type | Email | Status |
|------|------|-------|--------|
| John Smith | Individual | john.smith@email.com | Active |
| Jane Doe | Individual | jane.doe@email.com | Active |
| Tech Solutions LLC | Business | info@techsolutions.com | Active |

### Sample Documents Included

1. **W-2 (Form W-2 - Wage and Tax Statement)**
   - Employee: John Smith
   - Employer: ABC Corporation
   - Wages: $75,000.00
   - Federal Tax Withheld: $12,500.00
   - **Extraction Confidence: 96%**

2. **1040 (Individual Income Tax Return)**
   - Taxpayer: John Smith
   - Filing Status: Single
   - Total Income: $83,750 (from W-2 + interest + dividends)
   - Standard Deduction: $14,600
   - Taxable Income: $69,150
   - Expected Refund: $4,200
   - **Auto-fill Confidence: 97%**

3. **1099-INT (Interest Income)**
   - Source: First National Bank
   - Interest Income: $250.00
   - Federal Tax Withheld: $0.00
   - **Extraction Confidence: 98%**

## The Pipeline in Action

### Example: How John Smith's Tax Return is Processed

```
1. UPLOAD
   └─ John uploads W-2 PDF from ABC Corporation
   └─ Document stored with ID: doc-001-w2-2025
   
2. OCR EXTRACTION
   ├─ Extract employee info: "John M Smith"
   ├─ Extract wages: "$75,000.00" from Box 1
   ├─ Extract taxes withheld: "$12,500.00" from Box 2
   └─ Confidence Score: 96%
   
3. VALIDATION
   ├─ Check SSN format: ✓ Valid
   ├─ Check wage amounts: ✓ Reasonable
   ├─ Check tax withholding: ✓ Correct
   └─ Validation Score: 100%
   
4. AUTO-FILL
   ├─ New document: 1040 form (doc-002-1040-2025)
   ├─ Auto-fill Line 1a (wages): $75,000 (from W-2)
   ├─ Auto-fill Line 2 (interest): $250 (from 1099-INT)
   ├─ Auto-fill address: 123 Oak Street, New York, NY
   └─ Fields populated: 9 out of 14
   
5. CONFIDENCE SCORING
   ├─ High-confidence fields: 16
   ├─ Medium-confidence fields: 2
   ├─ Low-confidence fields: 0
   └─ Overall Score: 97%
   
6. CPA REVIEW
   ├─ Form status: "Ready for CPA Review"
   ├─ Assigned to: Jane CPA
   ├─ Expected completion: Dec 18, 2025
   └─ Next step: CPA approval or revision
```

## Key Data Files

### Database Tables

**clients** table
```
id          | entity_type | first_name | last_name | tax_id
-----------+-------------+------------+-----------+-----------
(uuid)      | individual  | John       | Smith     | 123-45-6789
(uuid)      | individual  | Jane       | Doe       | 987-65-4321
(uuid)      | business    | NULL       | NULL      | 45-6789012
            |             | (business_name: Tech Solutions LLC)
```

**ledger** table
```
document_id       | client_name | document_type | stage     | status
------------------+-------------+---------------+-----------+-----------
doc-001-w2-2025   | John Smith  | w2            | extracted | validated
doc-002-1040-2025 | John Smith  | 1040          | filled    | under_review
doc-003-1099int   | John Smith  | 1099_int      | extracted | validated
```

**enum_master** table
```
enum_type      | code       | label
---------------+------------+------------------
entity_type    | individual | Individual
entity_type    | business   | Business
filing_status  | single     | Single
filing_status  | mfj        | Married Filing Jointly
risk_profile   | low        | Low Risk
risk_profile   | medium     | Medium Risk
risk_profile   | high       | High Risk
```

### JSON Files in `backend/sample_data/`

```
sample_w2_extraction.json
├─ W-2 form as extracted by OCR
├─ Confidence scores for each field
├─ Employee info: SSN, name, address
├─ Employer info: EIN, company name
└─ Wage boxes: Box 1 = $75,000, Box 2 = $12,500, etc.

sample_1040_extraction.json
├─ Auto-filled 1040 form
├─ Source documents: W-2 + 1099-INT
├─ Line items with confidence scores
├─ Calculated values: Total Income, Tax, Refund
└─ Audit trail showing all transformations

sample_1099int_extraction.json
├─ 1099-INT form extraction
├─ Interest income: $250
├─ Payer info: First National Bank
├─ Recipient: John Smith
└─ Mapping to 1040 Line 2
```

## Common Tasks

### View Sample Client

```python
from backend.client_database.models import Client
from backend.client_database.database import get_db

db = get_db()
john = db.query(Client).filter(Client.first_name == "John").first()
print(f"{john.first_name} {john.last_name}")
print(f"Email: {john.email}")
print(f"Tax ID: {john.tax_id}")
```

### Load Sample Form Data

```python
import json

with open('backend/sample_data/sample_w2_extraction.json') as f:
    w2_data = json.load(f)

print(f"Form: {w2_data['form']}")
print(f"Year: {w2_data['year']}")
print(f"Wages (Box 1): ${w2_data['wage_information']['box_1_wages_tips_other_compensation']}")
print(f"Confidence: {w2_data['confidence'] * 100}%")
```

### Check Ledger for Documents

```bash
psql -U postgres -d ledger -c "
  SELECT document_id, document_type, stage, confidence_score
  FROM ledger
  WHERE client_name = 'John Smith'
  ORDER BY created_at DESC;
"
```

## Understanding Confidence Scores

The pipeline assigns confidence scores at each stage:

| Score | Meaning | Action |
|-------|---------|--------|
| 0.95+ | Excellent | Approve automatically |
| 0.85-0.94 | Good | Review by CPA |
| 0.75-0.84 | Fair | Flag for review + correction |
| <0.75 | Poor | Manual entry required |

**John Smith's Scores:**
- W-2 Extraction: **96%** (Approve)
- 1040 Auto-fill: **97%** (Approve)
- 1099-INT Extraction: **98%** (Approve)

## Testing Different Scenarios

### Scenario 1: Validate Extracted Data

```bash
# Test W-2 extraction validation
curl -X POST http://localhost:8000/api/validation/validate \
  -H "Content-Type: application/json" \
  -d '{
    "form_type": "W-2",
    "data": {
      "ssn": "123-45-6789",
      "wages": 75000,
      "tax_withheld": 12500
    }
  }'
```

### Scenario 2: Auto-Fill a Form

```bash
# Auto-fill 1040 from W-2 data
curl -X POST http://localhost:8000/api/forms/autofill \
  -H "Content-Type: application/json" \
  -d '{
    "target_form": "1040",
    "source_documents": ["doc-001-w2-2025"],
    "client_id": "john-smith-id"
  }'
```

### Scenario 3: Score a Filled Form

```bash
# Score the auto-filled form
curl -X POST http://localhost:8000/api/scoring/score \
  -H "Content-Type: application/json" \
  -d @backend/sample_data/sample_1040_extraction.json
```

## Next Steps

1. ✅ **Generated sample data** - Database populated with clients and enums
2. ✅ **Created form files** - Sample extracted data in JSON format
3. 📖 **Read the detailed guide** - See SAMPLE_DATA_README.md
4. 🧪 **Run tests** - Execute `python backend/tests/test_api.py`
5. 🔍 **Explore the code** - Review extraction and validation engines
6. 🚀 **Build features** - Customize for your use case

## Troubleshooting

### Database not found?
```bash
# Make sure databases exist
createdb client_database
createdb ledger

# Then run the data generator
python sample_pipeline_data.py
```

### Can't connect to PostgreSQL?
```bash
# Check if PostgreSQL is running
pg_isrunning  # or use your system's process viewer

# Start PostgreSQL (varies by OS)
# On macOS: brew services start postgresql
# On Linux: sudo systemctl start postgresql
# On Windows: Use Services app or `net start postgresql`
```

### API port 8000 already in use?
```bash
# Change the port in backend/main.py
# Or kill the process using the port
lsof -i :8000
kill -9 <PID>
```

## Documentation

- 📘 **[Detailed Sample Data Guide](./SAMPLE_DATA_README.md)** - Complete reference
- 🔧 **[Backend API Tests](./backend/tests/test_api.py)** - API examples
- 📊 **[Form Schemas](./backend/schemas/)** - Form definitions
- 🏗️ **[Architecture](./backend/adapters/)** - System components

## Summary

You now have:
- ✅ 3 sample clients in the database
- ✅ 10+ enum values for dropdowns
- ✅ 4 ledger entries tracking documents
- ✅ 3 sample form files (W-2, 1040, 1099-INT)
- ✅ Complete pipeline examples

**Ready to test the pipeline!** Start the API server and begin exploring.
