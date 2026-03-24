"""
preprocessor.py
===============
Stage 1b — Image preparation for scanned documents and photos.

Runs before OCR. Three operations in order:
  1. Deskew     — corrects rotation up to 45 degrees
  2. Denoise    — removes scanner grain and JPEG compression artifacts
  3. Upscale    — brings sub-200 DPI images up to 300 DPI equivalent

Input:  base64-encoded PNG string (as produced by pdf_router.py)
Output: base64-encoded PNG string (processed, same format)

Called by pdf_router.route_pdf_with_preprocessing() for scanned documents.
Not called by ocr_engine.py — Issue 22 (docstring corrected).
Not called on the digital path.

All operations are applied conservatively — if a step cannot run
cleanly (e.g. deskew finds no text pixels), it skips rather than
distorting the image. The original is always returned on any error.
"""

import cv2
import numpy as np
import base64
import logging

log = logging.getLogger(__name__)

# Minimum page width in pixels considered adequate for OCR.
# Below this, we upscale. 1700px ≈ 200 DPI on US Letter (8.5").
# 2550px ≈ 300 DPI — the sweet spot for PaddleOCR accuracy.
_TARGET_WIDTH_PX  = 2550
_MIN_WIDTH_PX     = 1700

# Deskew: only correct if the detected angle is within this range.
# Very small angles are noise; very large angles suggest the form
# is genuinely landscape or upside-down (different problem).
_MIN_SKEW_DEGREES = 0.5
_MAX_SKEW_DEGREES = 45.0


def preprocess_b64_image(b64_str: str) -> str:
    """
    Main entry point. Accepts and returns a base64 PNG string.

    Steps:
      decode → deskew → upscale → denoise → encode

    Returns the original string unchanged on any exception.
    """
    try:
        img_bytes = base64.b64decode(b64_str)
        img       = _decode_image(img_bytes)
        if img is None:
            return b64_str

        img = _deskew(img)
        img = _upscale(img)
        img = _denoise(img)

        _, buffer = cv2.imencode(".png", img)
        return base64.b64encode(buffer.tobytes()).decode("utf-8")

    except Exception as e:
        log.warning(f"[preprocessor] preprocessing failed, returning original: {e}")
        return b64_str


def preprocess_image_bytes(image_bytes: bytes) -> bytes:
    """
    Convenience wrapper for callers that work with raw bytes.
    """
    try:
        img = _decode_image(image_bytes)
        if img is None:
            return image_bytes

        img = _deskew(img)
        img = _upscale(img)
        img = _denoise(img)

        _, buffer = cv2.imencode(".png", img)
        return buffer.tobytes()

    except Exception as e:
        log.warning(f"[preprocessor] bytes preprocessing failed: {e}")
        return image_bytes


# ── Internal steps ────────────────────────────────────────────────────────────

def _decode_image(data: bytes):
    """Decode raw bytes to a BGR numpy array."""
    nparr = np.frombuffer(data, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        log.warning("[preprocessor] cv2.imdecode returned None — not a valid image")
    return img


def _deskew(img: np.ndarray) -> np.ndarray:
    """
    Detect and correct rotation using minAreaRect on text pixels.

    IRS forms are dense with horizontal text lines. The minimum
    bounding rectangle around all dark pixels gives a reliable
    skew angle estimate.
    """
    try:
        gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Threshold: isolate dark ink pixels
        _, binary = cv2.threshold(
            gray, 0, 255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )
        coords = np.column_stack(np.where(binary > 0))

        if len(coords) < 100:
            # Not enough dark pixels to estimate skew reliably
            return img

        angle = cv2.minAreaRect(coords)[-1]

        # minAreaRect returns angles in [-90, 0).
        # Convert to intuitive rotation angle.
        if angle < -45:
            angle = 90 + angle
        else:
            angle = angle  # already in (-45, 0] range, negate below

        # Flip sign: positive = clockwise skew needs counter-clockwise correction
        angle = -angle

        if not (_MIN_SKEW_DEGREES <= abs(angle) <= _MAX_SKEW_DEGREES):
            return img  # skip trivial or extreme angles

        (h, w) = img.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        rotated = cv2.warpAffine(
            img, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        log.debug(f"[preprocessor] deskewed {angle:.2f}°")
        return rotated

    except Exception as e:
        log.warning(f"[preprocessor] deskew failed: {e}")
        return img


def _upscale(img: np.ndarray) -> np.ndarray:
    """
    Upscale images below _MIN_WIDTH_PX to _TARGET_WIDTH_PX.

    Lanczos4 resampling preserves character edges better than
    bilinear or bicubic for small text.
    """
    h, w = img.shape[:2]
    if w >= _MIN_WIDTH_PX:
        return img

    scale  = _TARGET_WIDTH_PX / w
    new_w  = int(w * scale)
    new_h  = int(h * scale)
    scaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    log.debug(f"[preprocessor] upscaled {w}→{new_w}px ({scale:.1f}x)")
    return scaled


def _denoise(img: np.ndarray) -> np.ndarray:
    """
    Remove scanner grain and JPEG compression noise.

    Parameters are conservative — h=8 preserves thin characters
    while removing salt-and-pepper noise from scanner sensors.
    Higher h values blur character strokes and hurt OCR accuracy.
    """
    try:
        denoised = cv2.fastNlMeansDenoisingColored(
            img,
            None,
            h=8,            # luminance noise filter strength
            hColor=8,       # color noise filter strength
            templateWindowSize=7,
            searchWindowSize=21
        )
        return denoised
    except Exception as e:
        log.warning(f"[preprocessor] denoise failed: {e}")
        return img
