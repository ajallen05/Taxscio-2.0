# Taxscio Filling Pipeline - Sample Data Guide

This guide explains how to use the sample data to test and demonstrate the Taxscio filling pipeline.

## Overview

The Taxscio filling pipeline processes tax documents through the following stages:

```
Upload → OCR Extraction → Validation → Auto-Fill → Review → Finalization
```

## Quick Start

### 1. Generate Sample Database Data

First, ensure your databases are running:

```bash
# Start PostgreSQL and create databases
docker-compose up -d  # if using Docker

# Or connect to your local PostgreSQL
psql -U postgres
```

Then generate the sample data:

```bash
# From the project root directory
python sample_pipeline_data.py
```

This will:
- ✓ Create enum values (entity types, filing statuses, risk profiles, etc.)
- ✓ Insert 3 sample clients (individuals and a business)
- ✓ Create sample ledger entries for document tracking
- ✓ Generate JSON files with extracted form data

### 2. View Sample Extracted Data

The script creates sample form data files in `backend/sample_data/`:

```bash
ls backend/sample_data/
# sample_w2_extraction.json
# sample_1040_extraction.json
# sample_1099int_extraction.json
# pipeline_examples.py
```

### 3. Test the Pipeline

#### Option A: Using Python API

```python
from backend.adapters.extraction_engine import ExtractionEngine
from backend.adapters.validation import validate_form_data

# Load sample extracted data
import json
with open('backend/sample_data/sample_w2_extraction.json') as f:
    w2_data = json.load(f)

# Validate the extraction
validation_result = validate_form_data(w2_data)
print(f"Validation score: {validation_result['confidence_score']}")
print(f"Status: {validation_result['status']}")
```

#### Option B: Using API Endpoints

```bash
# Start the backend server
cd backend
python main.py

# In another terminal, test the API:

# 1. Upload and extract a form
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@backend/sample_data/sample_w2_extraction.json" \
  -F "client_id=john_smith_001"

# 2. Validate extracted data
curl -X POST http://localhost:8000/api/validation/validate \
  -H "Content-Type: application/json" \
  -d @backend/sample_data/sample_w2_extraction.json

# 3. Auto-fill form
curl -X POST http://localhost:8000/api/forms/autofill \
  -H "Content-Type: application/json" \
  -d '{
    "target_form": "1040",
    "source_documents": ["w2_extraction_001", "1099_int_extraction_001"],
    "client_id": "john_smith_001"
  }'
```

## Sample Data Structure

### 1. Sample Clients

Three sample clients are created:

1. **John Smith** (Individual)
   - Email: john.smith@email.com
   - Tax ID: 123-45-6789
   - Stage: Active Client
   - Risk Profile: Low
   - Documents: W-2, 1040, 1099-INT

2. **Jane Doe** (Individual)
   - Email: jane.doe@email.com
   - Tax ID: 987-65-4321
   - Stage: Active Client
   - Risk Profile: Medium
   - Documents: Multiple W-2s, 1099-NEC

3. **Tech Solutions LLC** (Business)
   - Tax ID: 45-6789012
   - Stage: Active Client
   - Risk Profile: Medium
   - Type: LLC
   - Documents: Various business forms

### 2. Sample Form Data

#### W-2 Extraction Example

```json
{
  "form": "W-2",
  "year": 2025,
  "employee_information": {
    "employee_ssn": "123-45-6789",
    "employee_first_name": "John",
    "employee_last_name": "Smith",
    "employee_address": "123 Oak Street",
    "employee_city": "New York",
    "employee_state": "NY",
    "employee_zip": "10001"
  },
  "employer_information": {
    "employer_tin": "12-3456789",
    "employer_name": "ABC Corporation",
    "employer_address": "100 Business Blvd"
  },
  "wage_information": {
    "box_1_wages_tips_other_compensation": 75000.00,
    "box_2_federal_income_tax_withheld": 12500.00,
    "box_5_medicare_wages_and_tips": 75000.00
  }
}
```

**Key Fields**:
- Box 1: Wages/Tips/Other Compensation = **$75,000.00**
- Box 2: Federal Income Tax Withheld = **$12,500.00**
- Box 5: Medicare Wages = **$75,000.00**

#### 1040 Auto-Fill Example

When the W-2 data flows into the 1040 form:

```json
{
  "form_id": "1040",
  "tax_year": 2025,
  "taxpayer_information": {
    "first_name": "John",
    "last_name": "Smith",
    "ssn": "123-45-6789"
  },
  "income": {
    "line_1a_total_wages": 75000.00,  // Auto-filled from W-2 Box 1
    "line_2_interest": 250.00,         // From 1099-INT
    "line_3_dividends": 1500.00        // Example entry
  }
}
```

### 3. Pipeline Stages and Data Flow

#### Stage 1: Upload
- **Input**: PDF file of tax document
- **Output**: Document stored with metadata
- **Status**: `file_uploaded`

#### Stage 2: OCR Extraction
- **Input**: Document PDF
- **Output**: Structured data with confidence scores
- **Status**: `extracted`
- **Example**: W-2 → Extracted JSON with employee info, wages, etc.

#### Stage 3: Validation
- **Input**: Extracted data
- **Output**: Validation report with scores
- **Status**: `validated` or `requires_correction`
- **Checks**: Field formats, required fields, business rules

#### Stage 4: Auto-Fill/Mapping
- **Input**: Validated extracted data
- **Output**: Populated form schema
- **Status**: `filled`
- **Example**: W-2 data → Auto-fills 1040 form lines

#### Stage 5: Confidence Scoring
- **Input**: Filled form data
- **Output**: Confidence scores and risk assessment
- **Status**: `scored`

#### Stage 6: CPA Review
- **Input**: Complete form with scores
- **Output**: Approved or flagged items
- **Status**: `ready_for_review` → `reviewing` → `approved`

## Sample Enum Values

The script creates predefined enum values for dropdown fields:

```python
Entity Types:
  - individual
  - business
  - trust

Filing Status:
  - single
  - married_filing_jointly
  - married_filing_separately
  - head_of_household

Risk Profiles:
  - low     (Green)
  - medium  (Orange)
  - high    (Red)

Document Types:
  - 1040 (Individual Income Tax)
  - W-2  (Wage and Tax Statement)
  - 1099-INT (Interest Income)
  - 1099-DIV (Dividends)
  - 1099-NEC (Nonemployee Compensation)
```

## Testing Different Scenarios

### Scenario 1: Single Filer with W-2 Income

**Sample Data**: John Smith
- Document: W-2 from ABC Corporation
- Income: $75,000
- Expected: Auto-fill 1040 as Single filer

```bash
python -c "
import json
from backend.sample_data.pipeline_examples import w2_extraction, form_1040_autofill
print('W-2 Confidence:', w2_extraction['confidence'])
print('1040 State:', form_1040_autofill['validation_summary']['status'])
"
```

### Scenario 2: Multiple Income Sources

**Sample Data**: John Smith + Interest Income
- Documents: W-2 + 1099-INT
- Expected: Combine income sources on 1040

```bash
# Use john Smith's data with interest income included
# Total income: $75,000 (W-2) + $250 (Interest) + $1,500 (Dividends) + $2,000 (Capital gains)
# = $78,750 total income
```

### Scenario 3: Freelancer with Multiple W-2s

**Sample Data**: Jane Doe
- Documents: Multiple W-2s from different employers
- Expected: Aggregate wages, combine on 1040

## Validating Sample Data

Check extraction quality:

```python
from backend.sample_data.pipeline_examples import w2_extraction

quality = w2_extraction['structured_data']['quality_metrics']
print(f"Page quality: {quality['page_quality']}")
print(f"Missing fields: {quality['missing_fields']}")
print(f"Field confidence scores:")
for field, score in quality['field_confidence_scores'].items():
    print(f"  {field}: {score * 100:.0f}%")
```

## Database Verification

After running the script, verify the data was inserted:

```bash
# Connect to client_database
psql -U postgres -d client_database

# Check clients
SELECT first_name, last_name, email, lifecycle_stage FROM clients;

# Check enums
SELECT enum_type, code, label FROM enum_master 
WHERE enum_type = 'filing_status';

# Check ledger entries
SELECT document_id, client_name, document_type, stage, status 
FROM ledger;
```

## Troubleshooting

### Database Connection Issues

```bash
# Check if PostgreSQL is running
psql -U postgres -c "SELECT version();"

# Verify databases exist
psql -U postgres -l | grep -E "client_database|ledger"

# If databases don't exist, run:
python sample_pipeline_data.py  # Will create and populate
```

### Extraction Confidence Too Low

The sample data includes high-confidence extractions (0.96+ for W-2). If testing validation:

```python
# Lower confidence values to test warning scenarios
w2_data['confidence'] = 0.75  # Triggers medium-confidence handling
```

### Missing Documents in Pipeline

Ensure all databases are created:

```bash
# Check PostgreSQL
psql -U postgres -d client_database -c "SELECT COUNT(*) FROM clients;"
psql -U postgres -d ledger -c "SELECT COUNT(*) FROM ledger;"
```

## Next Steps

1. **View the pipeline examples**: `python backend/sample_data/pipeline_examples.py`
2. **Run validation tests**: `python backend/tests/test_api.py`
3. **Test auto-fill mapping**: Use the extracted data with form mapper
4. **Review confidence scores**: Analyze the scoring engine results
5. **Export filled forms**: Generate completed tax forms from filled schemas

## Additional Resources

- [Form Schema Documentation](./backend/schemas/)
- [Extraction Engine](./backend/extraction/)
- [Validation Engine](./backend/validation/)
- [API Documentation](./backend/tests/test_api.py)

## Database Schema Reference

### clients table
- `id` (UUID): Client identifier
- `entity_type`: individual, business, trust
- `first_name`, `last_name`: Taxpayer names
- `tax_id`: SSN or EIN
- `email`, `phone`: Contact information
- `lifecycle_stage`: prospect, active_client, inactive
- `risk_profile`: low, medium, high

### ledger table
- `document_id`: Unique document identifier
- `document_type`: Form type (1040, W-2, etc.)
- `stage`: extracted, filled, validated, etc.
- `status`: Current processing status
- `confidence_score`: Extraction/filling confidence
- `tax_year`: Tax year for document

### enum_master table
- `enum_type`: Category of enumeration
- `code`: Unique code within type
- `label`: Display label for UI
- `is_active`: Whether enum is in use
