"""
nuextract_normalizer.py
=======================
Step 3 of the pipeline. Unified normalization layer for both PDF paths.

Takes input from EITHER:
  - text_extractor.py (digital path): structured Markdown string
  - qwen_client.py (scanned path): raw JSON string

Calls NuExtract PRO via the numind SDK to enforce the strict typed schema:
  - Coerces types:    "54,231.00" → 54231.00 (float)
  - Formats SSNs:     "123456789" → "123-45-6789"
  - Formats TINs:     "123456789" → "12-3456789"
  - Preserves nulls:  null → null
  - Enforces schema:  removes extra fields, adds missing fields as null

NuExtract works identically on both input types.
It maps field labels from Markdown tables and raw JSON values equally well.
This is what makes it the perfect unified normalization layer.
"""

import os
from numind import NuMind

client = NuMind(api_key=os.getenv("NUMIND_API_KEY"))


NUMIND_VALID_TYPES = {
    "verbatim-string", "string", "integer", "number",
    "boolean", "date", "datetime", "url", "email"
}

def to_nuextract_schema(obj):
    """
    Converts a null/false-based schema (used by Qwen as output guide) into
    NuMind's typed template format required by extract_structured_data().

    Rules:
        null                 → "verbatim-string"   (most text/string fields)
        false / true         → "boolean"           (checkboxes, flags)
        int (e.g. 2026)      → "integer"           (year, count fields)
        float                → "number"            (currency, amounts)
        known NuMind type    → kept as-is          (e.g. "verbatim-string")
        any other string     → "verbatim-string"   (concrete values like "1099-INT")
        list                 → each element converted
        dict                 → each value converted recursively
    """
    if isinstance(obj, dict):
        return {k: to_nuextract_schema(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_nuextract_schema(item) for item in obj]
    elif obj is None:
        return "verbatim-string"
    elif isinstance(obj, bool):
        return "boolean"
    elif isinstance(obj, int):
        return "integer"
    elif isinstance(obj, float):
        return "number"
    elif isinstance(obj, str):
        # Keep only recognised NuMind type annotations; convert anything else
        # (e.g. concrete values like "1099-INT", "IA", "W-2") to verbatim-string
        return obj if obj in NUMIND_VALID_TYPES else "verbatim-string"
    else:
        return "verbatim-string"


def normalize(schema: dict, input_text: str = None, input_file: bytes = None, instructions: str = "") -> dict:
    """
    Step 3: Normalize raw extraction text OR extract directly from a file (Vision) 
    into a strict typed dict via NuExtract PRO.

    Args:
        schema: The strict typed JSON schema for the form type
        input_text: Markdown string (digital path or OCR result)
        input_file: Raw PDF or Image bytes (vision path fallback)
        instructions: Optional guidance for the model

    Returns:
        Clean, typed dict with all fields normalized to schema spec.
    """
    # Convert null/false-based schema to NuMind typed format before API call
    typed_schema = to_nuextract_schema(schema)
    
    kwargs = {
        "template": typed_schema,
        "instructions": instructions
    }
    
    if input_file:
        kwargs["input_file"] = input_file
    else:
        kwargs["input_text"] = input_text or ""

    result = client.extract_structured_data(**kwargs)

    # numind SDK returns an ExtractionResponse object
    if hasattr(result, 'result') and isinstance(result.result, dict):
        return result.result
    elif hasattr(result, 'data'):
        return getattr(result, 'data')
    elif hasattr(result, 'extraction'):
        return getattr(result, 'extraction')
    elif hasattr(result, 'model_dump'):
        data = result.model_dump()
        return data.get('result', data)
    elif isinstance(result, dict):
        return result.get('result', result)
    else:
        return dict(result)
