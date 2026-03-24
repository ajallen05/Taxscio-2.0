"""
pdf_router.py
=============
Step 1 of the pipeline. Detects whether a PDF is digital (machine-generated)
or scanned (image-based), then routes to the correct extraction path.

DIGITAL: Contains embedded selectable text → use pymupdf4llm (fast, free, accurate)
         pymupdf_layout is imported first to activate its GNN layout engine, which
         improves heading detection, table reconstruction, and column ordering — all
         critical for multi-column IRS forms like the W-2.

SCANNED: Contains only images, no embedded text → use Qwen3-VL vision model (fallback)

Detection method:
  Extract text from page 1 with pymupdf.
  If len(text.strip()) > 50 characters → digital.
  If len(text.strip()) <= 50 characters → scanned.
"""

import fitz  # pymupdf
import base64
import io
from PIL import Image

# ── Activate pymupdf_layout BEFORE importing pymupdf4llm ──────────────────────
# pymupdf-layout installs itself as the sub-module pymupdf.layout.
# Importing it patches pymupdf4llm internally, enabling a GNN-based ONNX layout
# classifier that correctly handles multi-column layouts, tables and form fields.
try:
    import pymupdf.layout  # noqa: F401  — side-effect import only
    _layout_available = True
    print("[pdf_router] pymupdf.layout active — GNN layout analysis enabled.")
except ImportError:
    _layout_available = False
    print("[pdf_router] pymupdf.layout not found — using standard pymupdf4llm.")

import pymupdf4llm
# ─────────────────────────────────────────────────────────────────────────────


def route_pdf(pdf_bytes: bytes) -> tuple[str, object]:
    """
    Detect PDF type and extract content using the appropriate method.

    Returns:
      pdf_type = "digital" → Markdown string (all pages, layout-analysed)
      pdf_type = "scanned" → list of base64 PNG strings (all pages)
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Sample page 1 to determine PDF type
    first_page_text = doc[0].get_text().strip()
    is_digital = len(first_page_text) > 50

    if is_digital:
        try:
            # pymupdf4llm with layout analysis active (if pymupdf_layout is present).
            # page_chunks=False → single concatenated Markdown string for NuExtract.
            markdown_text = pymupdf4llm.to_markdown(
                doc,
                page_chunks=False,
            )
        except Exception as exc:
            print(f"[pdf_router] pymupdf4llm failed ({exc}), falling back to raw text.")
            # Graceful fallback: concatenate raw text from every page
            markdown_text = "\n\n".join(
                page.get_text("text") for page in doc
            )
        doc.close()
        return "digital", markdown_text
    else:
        # Scanned PDF: convert all pages to base64 PNG images for Qwen3-VL
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=150)  # 150 DPI sufficient for printed forms
            images.append(base64.b64encode(pix.tobytes("png")).decode("utf-8"))
        doc.close()
        return "scanned", images


def route_image(image_bytes: bytes, file_ext: str = "png") -> tuple[str, list[str]]:
    """
    Handle direct image upload by converting to base64 PNG using Pillow.
    Pillow supports WebP, JPG, and PNG natively, whereas PyMuPDF may lack codecs.
    """
    img = Image.open(io.BytesIO(image_bytes))

    # Convert to RGB if needed (e.g. for RGBA WebP/PNG)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return "scanned", [img_b64]


# ── New Stage 1 additions ──────────────────────────────────────────────────────

import re as _re
from backend.ingestion.preprocessor import preprocess_b64_image


def detect_form_boundaries(pdf_bytes: bytes) -> list:
    """
    Detect if a PDF contains multiple forms by scanning for OMB numbers.

    Each OMB number appearance (past page 0) signals a new form starting.
    Returns a list of (start_page, end_page) tuples (0-indexed, inclusive).

    Args:
        pdf_bytes: Raw PDF bytes.

    Returns:
        List of (start_page, end_page) tuples. Always contains at least one entry.
        Example: [(0, 1), (2, 3)] = two separate forms in a 4-page PDF.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        boundaries = []
        current_start = 0
        omb_pattern = _re.compile(r"OMB\s*No\.?\s*[\d-]+", _re.IGNORECASE)

        for i, page in enumerate(doc):
            text = page.get_text()
            if omb_pattern.search(text) and i > current_start:
                boundaries.append((current_start, i - 1))
                current_start = i

        boundaries.append((current_start, len(doc) - 1))
        doc.close()
        return boundaries

    except Exception:
        return [(0, -1)]  # treat as single form on any error


def route_pdf_with_preprocessing(pdf_bytes: bytes) -> tuple:
    """
    Drop-in replacement for route_pdf that adds OpenCV preprocessing for scans.

    Calls the existing route_pdf() then post-processes each scanned page image
    with deskew, upscale, and denoise. Digital PDFs are returned unchanged.

    Args:
        pdf_bytes: Raw PDF bytes.

    Returns:
        Same (pdf_type, content) tuple as route_pdf().
        For scanned: content is the preprocessed base64 image list.
    """
    pdf_type, content = route_pdf(pdf_bytes)

    if pdf_type == "scanned" and isinstance(content, list):
        processed = []
        for b64_img in content:
            try:
                processed.append(preprocess_b64_image(b64_img))
            except Exception:
                processed.append(b64_img)  # keep original on preprocessing failure
        return pdf_type, processed

    return pdf_type, content

