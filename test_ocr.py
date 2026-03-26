import logging
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath("."))

logging.basicConfig(level=logging.INFO)
try:
    from backend.ingestion.ocr_engine import _get_ocr
    print("Attempting to get OCR...")
    ocr = _get_ocr()
    print("Success!")
except Exception as e:
    print(f"Failed with error: {e}")
