"""
text_extractor.py
=================
Step 2A of the pipeline (digital PDF path only).

pymupdf_layout + pymupdf4llm have already extracted layout-aware Markdown in
pdf_router.py. This module adds form-specific context annotation so NuExtract
understands which IRS form it is reading and what field conventions to expect.
"""

# Per-form extraction hints sent to NuExtract as a system-level preamble.
# These align NuExtract's field-mapping heuristics with IRS box numbering.
_FORM_HINTS = {
    "W-2": (
        "This is an IRS W-2 Wage and Tax Statement. "
        "Fields are identified by Box numbers (Box 1 through Box 20). "
        "Employer data appears top-left; employee data appears below. "
        "Wage figures are in the centre grid; state data appears at the bottom."
    ),
    "1040": (
        "This is an IRS Form 1040 U.S. Individual Income Tax Return. "
        "Lines are numbered sequentially. Values appear to the right of each line label. "
        "Filing status checkboxes appear near the top. "
        "The form may span multiple pages."
    ),
    "1099-NEC": (
        "This is an IRS 1099-NEC Nonemployee Compensation form. "
        "Box 1 = nonemployee compensation. Box 4 = federal income tax withheld. "
        "Payer information is on the left; recipient information is on the right."
    ),
    "1099-INT": (
        "This is an IRS 1099-INT Interest Income form. "
        "Box 1 = interest income. Box 4 = federal income tax withheld. "
        "Payer is on the left; recipient TIN and address are below."
    ),
    "1099-DIV": (
        "This is an IRS 1099-DIV Dividends and Distributions form. "
        "Box 1a = total ordinary dividends. Box 1b = qualified dividends. "
        "Box 2a = total capital gain distributions."
    ),
    "1099-R": (
        "This is an IRS 1099-R Distributions from Pensions or IRAs. "
        "Box 1 = gross distribution. Box 2a = taxable amount. "
        "Box 7 = distribution code."
    ),
    "1099-MISC": (
        "This is an IRS 1099-MISC Miscellaneous Information form. "
        "Box 3 = other income. Box 4 = federal income tax withheld. "
        "Box 7 = nonemployee compensation (prior years)."
    ),
    "1099-B": (
        "This is an IRS 1099-B Proceeds from Broker Transactions. "
        "Box 1a = description of property. Box 1b = date acquired. "
        "Box 1d = proceeds. Box 1e = cost or other basis."
    ),
    "1099-G": (
        "This is an IRS 1099-G Government Payments form. "
        "Box 1 = unemployment compensation. Box 2 = state/local tax refunds. "
        "Box 4 = federal income tax withheld."
    ),
    "1099-K": (
        "This is an IRS 1099-K Payment Card and Third Party Network Transactions. "
        "Box 1a = gross amount of payment card/third party network transactions. "
        "Box 2 = merchant category code."
    ),
    "1099-S": (
        "This is an IRS 1099-S Proceeds from Real Estate Transactions. "
        "Box 2 = gross proceeds. Box 3 = address/legal description of property."
    ),
    "1098": (
        "This is an IRS 1098 Mortgage Interest Statement. "
        "Box 1 = mortgage interest received. Box 2 = outstanding mortgage principal. "
        "Box 3 = mortgage origination date."
    ),
    "1098-T": (
        "This is an IRS 1098-T Tuition Statement. "
        "Box 1 = payments received for qualified tuition. "
        "Box 5 = scholarships or grants."
    ),
    "SSA-1099": (
        "This is a Social Security Benefit Statement (SSA-1099). "
        "Box 3 = total Social Security benefits paid. "
        "Box 4 = benefits repaid to SSA."
    ),
}


def prepare_text_for_extraction(markdown_text: str, form_type: str) -> str:
    """
    Annotate layout-aware Markdown with an IRS form context preamble.

    The preamble tells NuExtract:
      - Which form it is reading
      - The box/line numbering convention used
      - Where key sections appear on the page

    This dramatically reduces field mis-mapping on multi-column forms.

    Args:
        markdown_text: Structured Markdown produced by pymupdf4llm + pymupdf_layout
        form_type: IRS form type string, e.g. "W-2"

    Returns:
        Preamble + Markdown string ready for NuExtract.

    Raises:
        ValueError: If markdown_text is empty or too short to contain real data.
    """
    if not markdown_text or len(markdown_text.strip()) < 20:
        raise ValueError("Extracted text is empty — PDF may be blank or corrupted.")

    form_preamble = _get_form_preamble(form_type)
    return f"{form_preamble}\n\n{markdown_text}"


def prepare_ocr_for_extraction(
    ocr_text: str,
    form_type: str,
    avg_confidence: float = 0.0,
) -> str:
    """
    Prepend an OCR-specific preamble to PaddleOCR output text.

    Used when the scanned path successfully processes a document with
    PaddleOCR instead of falling back to Qwen. The output format is
    the same as prepare_text_for_extraction() — a plain string — so
    NuExtract can consume it identically.

    Args:
        ocr_text:        The raw structured text from ocr_engine.run_ocr()["text"].
                         Already spatially organised (rows = horizontal form lines).
        form_type:       IRS form type string, e.g. "W-2". Used to select the
                         form-specific extraction instruction (same as
                         prepare_text_for_extraction uses).
        avg_confidence:  Average PaddleOCR word confidence for this document
                         (0.0–1.0). Included in the preamble so NuExtract
                         is aware of input quality.

    Returns:
        Complete string: OCR preamble + form preamble + OCR text.
        Ready to pass to nuextract_normalizer.extract().
    """
    # ── OCR source header ─────────────────────────────────────────────────────
    confidence_pct = f"{avg_confidence:.0%}" if avg_confidence else "unknown"
    ocr_header = (
        f"SOURCE: Scanned document processed by PaddleOCR "
        f"(confidence: {confidence_pct}).\n"
        f"FORMAT: Spatially reconstructed plain text. "
        f"Each line represents one horizontal row of the form. "
        f"Left-to-right column order is preserved within each line.\n"
        f"NOTE: Minor OCR noise may be present. "
        f"Prioritise values that pass IRS arithmetic rules "
        f"(e.g. SS tax = wages × 6.2%).\n\n"
    )

    # ── Form-specific extraction instruction ─────────────────────────────────
    form_preamble = _get_form_preamble(form_type)

    return f"{ocr_header}{form_preamble}\n\n{ocr_text}"


def _get_form_preamble(form_type: str) -> str:
    """
    Return the form-specific extraction instruction string for a given form type.
    """
    # Look up form-specific hint; fall back to a generic prompt
    hint = _FORM_HINTS.get(
        form_type,
        f"This is IRS Form {form_type}. Extract all labelled fields and numeric values exactly as printed.",
    )

    return (
        f"IRS Form: {form_type}\n"
        f"Extraction context: {hint}\n"
        f"\n---\n"
    )
