import re
import math
from typing import Optional

# ── Tuning ─────────────────────────────────────────────────────────────────────

# Minimum score to pass. 0–100.
# A single strong signal (OMB number) scores 40 alone.
# A form with OMB + form name + IRS agency scores 80+.
# Anything under 30 is almost certainly not a tax form.
GATE_THRESHOLD = 30

# Score weights per signal
_W_OMB_NUMBER      = 40   # OMB number is the strongest single signal
_W_FORM_NAME       = 25   # Known IRS form name
_W_IRS_AGENCY      = 20   # "Internal Revenue Service" or "Dept. of Treasury"
_W_TAX_YEAR        = 10   # 4-digit year in plausible tax range
_W_IRS_KEYWORDS    = 5    # Supporting keywords (wages, withholding, etc.)


# ── Known IRS form identifiers ─────────────────────────────────────────────────

_KNOWN_FORM_NAMES = [
    # Income statements
    "W-2", "W2",
    "W-2G", "W2G",
    "W-2C", "W2C",
    "1099-NEC",
    "1099-MISC",
    "1099-INT",
    "1099-DIV",
    "1099-R",
    "1099-B",
    "1099-S",
    "1099-G",
    "1099-K",
    "1099-SA",
    "1099-OID",
    "1099-Q",
    "1099-LTC",
    "1099-PATR",
    "1099-C",
    "1099-A",
    "1099-LS",
    "1099-SB",
    "SSA-1099",
    "RRB-1099",
    # Returns
    "1040",
    "1040-SR",
    "1040-NR",
    "1040-ES",
    "1040-X",
    "1040-SS",
    "1041",
    "1065",
    "1120",
    "1120-S",
    "1120-F",
    # Schedules
    "SCHEDULE A",
    "SCHEDULE B",
    "SCHEDULE C",
    "SCHEDULE D",
    "SCHEDULE E",
    "SCHEDULE SE",
    "SCHEDULE K-1",
    "K-1",
    # Informational / health
    "1095-A",
    "1095-B",
    "1095-C",
    "1098",
    "1098-T",
    "1098-E",
    "1098-C",
    # Employment tags
    "940",
    "941",
    "944",
    "945",
    "W-3",
    "W-4",
    "W-9",
]

# Pre-compute a robust regex that handles optional hyphens/spaces
_form_regex_parts = []
for f in sorted(_KNOWN_FORM_NAMES, key=len, reverse=True):
    # e.g., "W-2" -> "W[\s\-]*2"
    pattern = r'[\s\-]*'.join(re.escape(char) for char in f if char not in ('-', ' '))
    _form_regex_parts.append(pattern)

_FORM_PATTERN = re.compile(
    r'\b(?:Form\s+)?(' + '|'.join(_form_regex_parts) + r')\b',
    re.IGNORECASE
)

_OMB_PATTERN = re.compile(
    r'(?:OMB\s*(?:No\.?|#|Number)?\s*)?'
    r'\b(1[0-9]{3}-[0-9]{4})\b',
    re.IGNORECASE
)

_AGENCY_PATTERNS = [
    re.compile(r'internal\s+revenue\s+service', re.IGNORECASE),
    re.compile(r'department\s+of\s+the\s+treasury', re.IGNORECASE),
    re.compile(r'u\.?s\.?\s+treasury', re.IGNORECASE),
]

_YEAR_PATTERN = re.compile(r'\b(19[9][0-9]|20[0-2][0-9]|203[0-5])\b')

_IRS_KEYWORDS = re.compile(
    r'\b(?:'
    r'wages?|withholding|taxable|federal\s+income\s+tax|'
    r'social\s+security|medicare|employer|employee|'
    r'omb|ein|tin|ssn|taxpayer|payer|recipient|'
    r'adjusted\s+gross\s+income|deduction|exemption|'
    r'box\s+\d+[a-z]?|irs\.gov|void|corrected'
    r')\b',
    re.IGNORECASE
)


def _score_text(text: str) -> dict:
    score       = 0
    signals     = []
    form_type   = None
    tax_year    = None
    omb_number  = None

    if not text or len(text.strip()) < 10:
        return {
            "score": 0,
            "is_tax_form": False,
            "rejection_reason": "Insufficient text extracted to identify document."
        }

    omb_match = _OMB_PATTERN.search(text)
    if omb_match:
        omb_number = omb_match.group(1)
        score += _W_OMB_NUMBER
        signals.append(f"OMB: {omb_number}")

    form_match = _FORM_PATTERN.search(text)
    if form_match:
        form_type = form_match.group(1).upper()
        score += _W_FORM_NAME
        signals.append(f"Form: {form_type}")

    for pattern in _AGENCY_PATTERNS:
        if pattern.search(text):
            score += _W_IRS_AGENCY
            signals.append("IRS Agency identified")
            break

    year_match = _YEAR_PATTERN.search(text)
    if year_match:
        tax_year = int(year_match.group(1))
        score += _W_TAX_YEAR
        signals.append(f"Year: {tax_year}")

    keyword_count = len(_IRS_KEYWORDS.findall(text))
    if keyword_count >= 3:
        score += _W_IRS_KEYWORDS
        signals.append(f"IRS Keywords ({keyword_count})")

    is_tax_form = score >= GATE_THRESHOLD

    return {
        "score": score,
        "is_tax_form": is_tax_form,
        "form_type": form_type,
        "tax_year": tax_year,
        "omb_number": omb_number,
        "signals_found": signals,
        "rejection_reason": None if is_tax_form else "Document recognition confidence too low."
    }


def verify_is_tax_form_from_text(text: str) -> dict:
    return _score_text(text)


def verify_is_tax_form_from_pdf(pdf_bytes: bytes) -> dict:
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        
        # If the extracted text from PDF is barely anything or seems like garbage (often from scanned PDFs)
        # We should fail open rather than explicitly rejecting it, letting OCR do the actual extraction
        if len(text.strip()) < 50:
             return {"is_tax_form": True, "score": -1, "error": "Insufficient text for gate classification, assuming scanned PDF"}
             
        return _score_text(text)
    except Exception as e:
        # Fail open
        return {"is_tax_form": True, "score": -1, "error": str(e)}


def verify_is_tax_form(document_source: dict) -> dict:
    """
    Legacy compatibility wrapper. 
    Accepts: {"type": "text", "content": str} or {"type": "image", "content": str}
    """
    if document_source.get("type") == "text":
        return verify_is_tax_form_from_text(document_source.get("content", ""))

    # Image-only: fail-open for legacy compatibility as we cannot score without text here
    return {
        "is_tax_form": True,
        "form_type": None,
        "tax_year": None,
        "omb_number": None,
        "score": -1,
        "signals_found": [],
        "rejection_reason": None,
        "_note": "Image-type gate requires OCR text pass. Failing open."
    }
