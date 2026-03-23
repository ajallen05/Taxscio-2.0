"""
ocr_engine.py
=============
Stage 2B — OCR extraction for scanned documents and photos.

Replaces qwen_client.py as the primary scanned-path extractor.

WHAT IT DOES:
  Takes a list of base64 PNG pages (same format pdf_router.py already produces),
  runs PaddleOCR on each page, and returns a single structured text string
  in the same format that text_extractor.prepare_text_for_extraction() expects.

  The output feeds directly into NuExtract — identical to the digital PDF path.
  Both paths are now unified at NuExtract.

FALLBACK:
  If PaddleOCR returns overall page confidence below OCR_CONFIDENCE_THRESHOLD
  (default 0.80), the engine raises LowConfidenceError.
  The caller (main.py) catches this and falls back to qwen_client.py.
  This keeps Qwen available for genuinely degraded documents without
  paying for it on clean scans.

SPATIAL LAYOUT PRESERVATION:
  PaddleOCR returns bounding boxes for every word. We use these to
  reconstruct approximate spatial layout — grouping words by Y position
  into rows, preserving left-to-right column order within each row.

  For IRS forms this is critical. A W-2 has two employer sections side
  by side. Without spatial grouping, the text stream merges them.
  With Y-row grouping, each horizontal band is preserved as a line.

INSTALLATION:
  pip install paddlepaddle paddleocr

  CPU-only (no GPU required):
  pip install paddlepaddle paddleocr

  The first run downloads model weights (~200MB). Subsequent runs use cache.
"""

import base64
import logging
import re
from io import BytesIO
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

# Issue 2 / config.py: threshold now also declared in backend/config.py.
# Kept here for backward compatibility — any caller that imports this
# constant directly from ocr_engine still gets the right value.
from backend.config import config as _config
OCR_CONFIDENCE_THRESHOLD = _config.ocr_confidence_threshold

# Y-axis tolerance for grouping words into the same row (pixels).
# Words whose top-y coordinates differ by less than this are treated
# as being on the same line.
ROW_Y_TOLERANCE = 8


class LowConfidenceError(Exception):
    """
    Raised when PaddleOCR confidence falls below OCR_CONFIDENCE_THRESHOLD.
    Signals main.py to fall back to qwen_client.py for this document.
    """
    def __init__(self, confidence: float, page: int):
        self.confidence = confidence
        self.page = page
        super().__init__(
            f"PaddleOCR page {page} confidence {confidence:.0%} "
            f"below threshold {OCR_CONFIDENCE_THRESHOLD:.0%}"
        )


# Initialize PaddleOCR immediately to avoid slow first-request loading and hangs
try:
    from paddleocr import PaddleOCR
    _paddle_ocr = PaddleOCR(
        use_angle_cls=True,
        lang="en",
    )
    log.info("[ocr_engine] PaddleOCR initialised eagerly (CPU mode)")
except Exception as e:
    # Give a detailed error if missing
    log.error(f"[ocr_engine] PaddleOCR initialisation FAILED: {str(e)}")
    import traceback
    log.error(traceback.format_exc())
    _paddle_ocr = None

def _get_ocr():
    if _paddle_ocr is None:
        raise ImportError(
            "PaddleOCR is not installed. Run: pip install paddlepaddle paddleocr"
        )
    return _paddle_ocr


# ── Public API ────────────────────────────────────────────────────────────────

def run_ocr(
    page_images: list,
    form_type: str,
    raise_on_low_confidence: bool = True,
) -> dict:
    """
    Run PaddleOCR on a list of base64 PNG pages.

    Args:
        page_images:              List of base64 PNG strings (from pdf_router.py).
        form_type:                IRS form type string, e.g. "W-2". Used in output header.
        raise_on_low_confidence:  If True, raises LowConfidenceError when confidence
                                  falls below OCR_CONFIDENCE_THRESHOLD. Set False to
                                  always return results regardless of quality.

    Returns:
        {
            "text":            str  — structured text ready for text_extractor.py,
            "min_confidence":  float — lowest per-page confidence (0.0–1.0),
            "avg_confidence":  float — average per-page confidence,
            "page_count":      int,
            "word_count":      int,
        }

    Raises:
        LowConfidenceError: if any page confidence < OCR_CONFIDENCE_THRESHOLD
                            and raise_on_low_confidence is True.
        ImportError:        if paddleocr is not installed.
    """
    ocr     = _get_ocr()
    pages   = []
    all_confidences = []

    for page_num, b64_str in enumerate(page_images, start=1):
        try:
            img_array = _b64_to_numpy(b64_str)
        except Exception as e:
            log.warning(f"[ocr_engine] page {page_num} decode failed: {e}")
            continue

        # Run OCR on this page
        # Returns: list of [[[x1,y1],[x2,y2],[x3,y3],[x4,y4]], (text, confidence)]
        raw_result = ocr.ocr(img_array, cls=True)

        if not raw_result or raw_result[0] is None:
            log.warning(f"[ocr_engine] page {page_num} returned no results")
            pages.append({"page": page_num, "words": [], "confidence": 0.0, "text": ""})
            all_confidences.append(0.0)
            continue

        # PaddleOCR returns a list of lists (one per image in batch)
        # We pass one image at a time, so raw_result[0] is our page
        detections = raw_result[0]

        words, page_confidence = _parse_detections(detections, page_num)

        # Issue 8 FIXED: do NOT raise per-page.  Collect all page confidences
        # first, then decide based on the document-level average.  A single
        # degraded page in a multi-page form no longer forces a full fallback
        # when the rest of the document is clean.
        page_text = _words_to_structured_text(words, page_num, len(page_images))
        pages.append({
            "page":       page_num,
            "words":      words,
            "confidence": page_confidence,
            "text":       page_text,
        })
        all_confidences.append(page_confidence)

    # Combine all pages into one text block
    full_text   = "\n\n".join(p["text"] for p in pages if p["text"])
    total_words = sum(len(p["words"]) for p in pages)
    min_conf    = min(all_confidences) if all_confidences else 0.0
    avg_conf    = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

    # Raise only after all pages are processed — based on document-level average
    if raise_on_low_confidence and avg_conf < OCR_CONFIDENCE_THRESHOLD:
        raise LowConfidenceError(avg_conf, page_num=0)  # page_num=0 = document-level

    log.info(
        f"[ocr_engine] {form_type} | {len(pages)} page(s) | "
        f"{total_words} words | confidence min={min_conf:.0%} avg={avg_conf:.0%}"
    )

    return {
        "text":           full_text,
        "min_confidence": min_conf,
        "avg_confidence": avg_conf,
        "page_count":     len(pages),
        "word_count":     total_words,
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _b64_to_numpy(b64_str: str) -> np.ndarray:
    """Decode a base64 PNG string to a BGR numpy array for OpenCV/PaddleOCR."""
    from PIL import Image
    img_bytes = base64.b64decode(b64_str)
    pil_img   = Image.open(BytesIO(img_bytes)).convert("RGB")
    return np.array(pil_img)


def _parse_detections(detections: list, page_num: int) -> tuple:
    """
    Parse PaddleOCR raw detections into a list of word dicts.

    PaddleOCR detection format:
        [ [ [[x1,y1],[x2,y2],[x3,y3],[x4,y4]], (text, confidence) ], ... ]

    Returns:
        (words: list, page_confidence: float)

    Each word dict:
        {
            "text":       str,
            "confidence": float,
            "x0":         float,  ← left edge of bounding box
            "y0":         float,  ← top edge of bounding box
            "x1":         float,  ← right edge
            "y1":         float,  ← bottom edge
        }
    """
    words = []
    confidences = []

    for detection in detections:
        if not detection or len(detection) < 2:
            continue

        bbox_points = detection[0]   # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        text_conf   = detection[1]   # (text, confidence)

        if not text_conf or len(text_conf) < 2:
            continue

        text       = str(text_conf[0]).strip()
        confidence = float(text_conf[1])

        if not text:
            continue

        # Extract bounding box: top-left and bottom-right corners
        xs = [pt[0] for pt in bbox_points]
        ys = [pt[1] for pt in bbox_points]
        x0, y0 = min(xs), min(ys)
        x1, y1 = max(xs), max(ys)

        words.append({
            "text":       text,
            "confidence": confidence,
            "x0":         x0,
            "y0":         y0,
            "x1":         x1,
            "y1":         y1,
        })
        confidences.append(confidence)

    page_confidence = (
        sum(confidences) / len(confidences)
        if confidences else 0.0
    )

    return words, page_confidence


def _words_to_structured_text(
    words: list,
    page_num: int,
    total_pages: int,
) -> str:
    """
    Convert a list of word dicts (with bounding boxes) into structured text
    that preserves the spatial layout of the form.

    Algorithm:
      1. Sort words by Y position (top to bottom).
      2. Group words into rows: words whose Y0 values differ by less than
         ROW_Y_TOLERANCE pixels are on the same horizontal line.
      3. Within each row, sort by X position (left to right).
      4. Join words in each row with spaces.
      5. Join rows with newlines.

    This preserves the two-column layout of forms like W-2 where boxes
    sit side-by-side horizontally.
    """
    if not words:
        return f"[Page {page_num} of {total_pages} — no text detected]"

    # Sort by vertical position first
    sorted_words = sorted(words, key=lambda w: (w["y0"], w["x0"]))

    # Group into rows
    rows = []
    current_row = [sorted_words[0]]
    current_y   = sorted_words[0]["y0"]

    for word in sorted_words[1:]:
        if abs(word["y0"] - current_y) <= ROW_Y_TOLERANCE:
            current_row.append(word)
        else:
            rows.append(current_row)
            current_row = [word]
            current_y   = word["y0"]
    rows.append(current_row)

    # Build text lines — sort each row by X position
    lines = [f"[Page {page_num} of {total_pages}]"]
    for row in rows:
        row_sorted = sorted(row, key=lambda w: w["x0"])
        line       = "  ".join(w["text"] for w in row_sorted)
        lines.append(line)

    return "\n".join(lines)


# Issue 26: format_ocr_for_extraction() was dead code — main.py calls
# prepare_ocr_for_extraction() from text_extractor directly.  Removed.
