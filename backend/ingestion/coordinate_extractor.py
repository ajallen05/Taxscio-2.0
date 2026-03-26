"""
coordinate_extractor.py
=======================
Stage 1 supplement for the digital PDF path only.

pdfplumber extracts every word from a digital PDF with its exact X/Y coordinates.
This spatial data is formatted into a structured string and prepended to the
pymupdf4llm Markdown before NuExtract sees it.

WHY THIS MATTERS:
The current digital path collapses a 2D tax form into 1D markdown.
pdfplumber's coordinate data directly eliminates the dominant failure mode on
digital W-2s: values bting mapped to the wrong box because Box 1 and Box 2
sit side-by-side and lose spatial separation in linear text.

Graceful fallback: returns empty string on any failure, so the existing
markdown-only path continues to work.
"""

from io import BytesIO

try:
    import pdfplumber
    _PDFPLUMBER_AVAILABLE = True
except ImportError:
    _PDFPLUMBER_AVAILABLE = False
    print("[coordinate_extractor] pdfplumber not installed — spatial extraction disabled. "
          "Run: pip install pdfplumber")


def extract_coordinates(pdf_bytes: bytes) -> list:
    """
    Extract every word from a digital PDF with its exact page position.

    Args:
        pdf_bytes: Raw PDF bytes.

    Returns:
        List of word dicts:
        [
            {
                "text": "44629.35",
                "x0": 312.4, "y0": 187.1,
                "x1": 358.2, "y1": 199.8,
                "page": 1,
                "page_width": 612.0, "page_height": 792.0
            },
            ...
        ]
        Returns [] on any failure (caller falls back to markdown-only).
    """
    if not _PDFPLUMBER_AVAILABLE:
        return []

    words = []
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages):
                extracted = page.extract_words(
                    x_tolerance=3,
                    y_tolerance=3,
                    keep_blank_chars=False,
                    use_text_flow=False
                )
                for word in extracted:
                    words.append({
                        "text":        word["text"],
                        "x0":          round(word["x0"],     1),
                        "y0":          round(word["top"],    1),
                        "x1":          round(word["x1"],     1),
                        "y1":          round(word["bottom"], 1),
                        "page":        page_num + 1,
                        "page_width":  round(page.width,  1),
                        "page_height": round(page.height, 1),
                    })
    except Exception as e:
        print(f"[coordinate_extractor] Failed: {e}")
        return []

    return words


def format_coordinates_for_prompt(words: list, form_type: str) -> str:
    """
    Convert word-coordinate list into a structured string for NuExtract.

    Groups words into rows by Y-coordinate proximity (within 5 points).
    Sorts each row left-to-right by X position to preserve column structure.

    Args:
        words: Output of extract_coordinates().
        form_type: IRS form type, e.g. "W-2" (used in header only).

    Returns:
        Multi-line string with spatial layout. Empty string if words is empty.
    """
    if not words:
        return ""

    # Group words into rows: words within 5pt of each other vertically are same row
    rows = []
    current_row = []
    current_y = None

    for word in sorted(words, key=lambda w: (w["page"], w["y0"], w["x0"])):
        if current_y is None or abs(word["y0"] - current_y) > 5:
            if current_row:
                rows.append(current_row)
            current_row = [word]
            current_y = word["y0"]
        else:
            current_row.append(word)

    if current_row:
        rows.append(current_row)

    # Format as human-readable spatial layout
    lines = [f"SPATIAL LAYOUT — {form_type}"]
    lines.append("(Format: [x_position] text — preserves left-to-right column structure)")
    lines.append("")

    current_page = None
    for row in rows:
        page_num = row[0]["page"]
        if page_num != current_page:
            current_page = page_num
            lines.append(f"--- Page {current_page} ---")

        row_str = "  ".join(
            f"[{w['x0']:.0f}] {w['text']}"
            for w in sorted(row, key=lambda w: w["x0"])
        )
        lines.append(row_str)

    return "\n".join(lines)
