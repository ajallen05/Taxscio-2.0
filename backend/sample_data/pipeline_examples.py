"""
Sample extracted form data for demonstrating the filling pipeline.
This shows real-world examples of OCR-extracted form data that flows through the pipeline.
"""

# Sample 1: W-2 Form Extraction
# This is what the OCR engine extracts from a W-2 PDF
w2_extraction = {
    "form_type": "W-2",
    "confidence": 0.96,
    "extracted_at": "2025-12-15T10:30:00Z",
    "source": "ocr_engine",
    "raw_text": """
    Form W-2
    22222 2025
    c Control number: 001
    a Employee's SSN: 123-45-6789
    b Employer's EIN: 12-3456789
    d Employee's address: 123 Oak Street, New York, NY 10001
    e Employee's first name and initial: John M
    f Employee's last name: Smith
    g Employer's name and address: ABC Corporation, 100 Business Blvd, New York, NY 10005
    1 Wages, tips, other compensation: 75,000.00
    2 Federal income tax withheld: 12,500.00
    3 Social security wages: 75,000.00
    4 Social security tax withheld: 4,650.00
    5 Medicare wages and tips: 75,000.00
    6 Medicare tax withheld: 1,087.50
    13 Retirement plan: X
    """,
    "structured_data": {
        "employee": {
            "ssn": "123-45-6789",
            "first_name": "John",
            "middle_initial": "M",
            "last_name": "Smith",
            "address": "123 Oak Street",
            "city": "New York",
            "state": "NY",
            "zip": "10001"
        },
        "employer": {
            "ein": "12-3456789",
            "name": "ABC Corporation",
            "address": "100 Business Blvd",
            "city": "New York",
            "state": "NY",
            "zip": "10005"
        },
        "wages": {
            "box_1": 75000.00,
            "box_2": 12500.00,
            "box_3": 75000.00,
            "box_4": 4650.00,
            "box_5": 75000.00,
            "box_6": 1087.50,
            "box_7": 0.00,
        },
        "checkboxes": {
            "retirement_plan": True,
            "statutory_employee": False,
            "third_party_sick_pay": False
        },
        "quality_metrics": {
            "field_confidence_scores": {
                "ssn": 0.99,
                "ein": 0.98,
                "box_1": 0.95,
                "box_2": 0.96,
                "box_5": 0.97,
                "employee_name": 0.93,
            },
            "missing_fields": [],
            "ambiguous_fields": [],
            "page_quality": 0.96,
        }
    }
}

# Sample 2: 1040 Form Auto-Fill Pipeline
# This shows how extracted W-2 data flows into 1040 form
form_1040_autofill = {
    "form_type": "1040",
    "tax_year": 2025,
    "source_documents": ["w2_extraction_001", "1099_int_extraction_001"],
    "filled_at": "2025-12-16T14:22:00Z",
    "auto_filled_by": "data_mapper_engine",
    "fill_strategy": "merge_multiple_sources",
    "sections": {
        "taxpayer_info": {
            "first_name": {"value": "John", "source": "w2_extraction", "confidence": 0.99},
            "middle_initial": {"value": "M", "source": "w2_extraction", "confidence": 0.93},
            "last_name": {"value": "Smith", "source": "w2_extraction", "confidence": 0.99},
            "ssn": {"value": "123-45-6789", "source": "w2_extraction", "confidence": 0.99},
            "address": {"value": "123 Oak Street", "source": "w2_extraction", "confidence": 0.99},
            "city": {"value": "New York", "source": "w2_extraction", "confidence": 0.99},
            "state": {"value": "NY", "source": "w2_extraction", "confidence": 0.99},
            "zip": {"value": "10001", "source": "w2_extraction", "confidence": 0.99},
        },
        "filing_status": {
            "filing_status": {
                "selected": "single",
                "source": "client_profile",
                "confidence": 1.0,
                "requires_review": False
            }
        },
        "income": {
            "line_1a_wages": {
                "value": 75000.00,
                "source": "w2_extraction",
                "confidence": 0.95,
                "requires_review": False,
                "notes": "Extracted from W-2 Box 1"
            },
            "line_2_interest": {
                "value": 250.00,
                "source": "1099_int_extraction",
                "confidence": 0.98,
                "requires_review": False,
                "notes": "Extracted from 1099-INT Box 1"
            },
            "total_income": {
                "value": 75250.00,
                "source": "calculated",
                "confidence": 1.0,
                "requires_review": False,
                "calculation": "line_1a + line_2"
            }
        },
        "deductions": {
            "standard_deduction": {
                "value": 14600,
                "source": "standard_irs_table",
                "confidence": 1.0,
                "requires_review": False,
                "notes": "2025 Standard Deduction for Single Filer"
            },
            "taxable_income": {
                "value": 60650.00,
                "source": "calculated",
                "confidence": 1.0,
                "requires_review": False,
                "calculation": "total_income - standard_deduction"
            }
        }
    },
    "validation_summary": {
        "valid_fields": 12,
        "requires_review_fields": 0,
        "missing_required_fields": 0,
        "confidence_score": 0.97,
        "status": "ready_for_cpa_review"
    }
}

# Sample 3: Data Flow Through Pipeline
pipeline_flow_example = {
    "document_id": "doc-001-w2-2025",
    "client_name": "John Smith",
    "tax_year": 2025,
    "stages": {
        "1_upload": {
            "timestamp": "2025-12-15T08:00:00Z",
            "status": "completed",
            "file_info": {
                "filename": "w2_2025_john_smith.pdf",
                "size_bytes": 245000,
                "page_count": 1,
                "file_hash": "sha256:abc123..."
            },
            "output": "ready_for_ocr"
        },
        "2_ocr_extraction": {
            "timestamp": "2025-12-15T08:05:00Z",
            "status": "completed",
            "engine": "tesseract_plus",
            "confidence": 0.96,
            "extracted_fields": {
                "count": 18,
                "high_confidence": 16,  # >0.95
                "medium_confidence": 2,  # 0.85-0.95
                "low_confidence": 0,  # <0.85
            },
            "output": {
                "structured_data": w2_extraction["structured_data"],
                "quality_metrics": w2_extraction["structured_data"]["quality_metrics"]
            }
        },
        "3_validation": {
            "timestamp": "2025-12-15T08:10:00Z",
            "status": "completed",
            "validator": "data_integrity_engine",
            "checks_performed": [
                "required_fields_present",
                "field_format_validation",
                "cross_field_consistency",
                "tax_rule_compliance"
            ],
            "issues_found": {
                "errors": [],
                "warnings": [],
                "info": ["Employer EIN seems valid", "SSN format correct"]
            },
            "validation_score": 1.0,
            "output": "validated_and_ready_for_autofill"
        },
        "4_auto_mapping": {
            "timestamp": "2025-12-15T08:15:00Z",
            "status": "completed",
            "target_form": "1040",
            "mapper": "intelligent_form_mapper",
            "mappings_applied": [
                "W-2_Box1_to_1040_Line1a",
                "Employee_SSN_to_Taxpayer_SSN",
                "W-2_Address_to_1040_Address"
            ],
            "fields_populated": 9,
            "fields_requiring_input": 5,
            "output": form_1040_autofill
        },
        "5_confidence_scoring": {
            "timestamp": "2025-12-15T08:20:00Z",
            "status": "completed",
            "scorer": "ml_confidence_scorer",
            "field_scores": {
                "low_confidence_fields": [],
                "medium_confidence_fields": [],
                "high_confidence_fields": [
                    "wages", "ssn", "employer_ein", "employee_info"
                ]
            },
            "overall_score": 0.97,
            "recommendation": "approve_and_proceed"
        },
        "6_cpa_review": {
            "timestamp": "2025-12-15T14:00:00Z",
            "status": "in_progress",
            "assigned_to": "jane.cpa@firm.com",
            "notes": "Reviewing auto-filled 1040 form",
            "approval_status": "pending"
        }
    },
    "summary": {
        "document_class": "primary_income_document",
        "processing_time_seconds": 1200,
        "steps_completed": 5,
        "next_action": "awaiting_cpa_approval",
        "documents_waiting_for_review": 3
    }
}

# Sample 4: Batch Processing Multiple Documents
batch_processing_example = {
    "batch_id": "batch_20251215_001",
    "client_name": "John Smith",
    "tax_year": 2025,
    "created_at": "2025-12-15T08:00:00Z",
    "total_documents": 5,
    "documents": [
        {
            "document_id": "doc-001",
            "type": "W-2",
            "status": "completed",
            "confidence": 0.96,
            "notes": "Primary W-2 from ABC Corporation"
        },
        {
            "document_id": "doc-002",
            "type": "1099-INT",
            "status": "completed",
            "confidence": 0.98,
            "notes": "Interest income statement"
        },
        {
            "document_id": "doc-003",
            "type": "1099-DIV",
            "status": "completed",
            "confidence": 0.94,
            "notes": "Dividend income statement"
        },
        {
            "document_id": "doc-004",
            "type": "1040",
            "status": "in_progress",
            "confidence": 0.97,
            "notes": "Auto-filled using docs 001-003"
        },
        {
            "document_id": "doc-005",
            "type": "Schedule C",
            "status": "waiting",
            "confidence": None,
            "notes": "Requires manual entry of business information"
        }
    ],
    "summary": {
        "fully_automated": 3,
        "partially_automated": 1,
        "manual_entry_required": 1,
        "estimated_completion": "2025-12-18"
    }
}

if __name__ == "__main__":
    import json
    
    print("Sample Pipeline Data Examples")
    print("=" * 70)
    print("\n1. W-2 Extraction (OCR Output)")
    print(json.dumps(w2_extraction, indent=2))
    
    print("\n2. 1040 Auto-Fill (Data Mapper Output)")
    print(json.dumps(form_1040_autofill, indent=2))
    
    print("\n3. Complete Pipeline Flow")
    print(json.dumps(pipeline_flow_example, indent=2))
    
    print("\n4. Batch Processing Example")
    print(json.dumps(batch_processing_example, indent=2))
