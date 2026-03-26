"""
backend/adapters/ocr.py
=======================
Adapter wrapping ocr_engine.py for future extraction as the Extraction Engine
microservice.

The OCR pipeline — PaddleOCR primary, NuExtract Vision fallback — is an
internal concern of the Extraction Engine.  This adapter exposes it as a
clean interface so the service boundary is clear.
"""

from backend.ingestion.ocr_engine import run_ocr, LowConfidenceError


class OCRAdapter:
    """
    Wraps ocr_engine.py for Extraction Engine extraction.

    The PaddleOCR → NuExtract Vision fallback architecture is deliberately
    preserved.  Do not collapse to a single model path.
    """

    def run(
        self,
        page_images: list,
        form_type: str,
        raise_on_low_confidence: bool = True,
    ) -> dict:
        """
        Run PaddleOCR on a list of base64 PNG page images.

        Args:
            page_images:             List of base64 PNG strings.
            form_type:               IRS form type (used in log output).
            raise_on_low_confidence: Raise LowConfidenceError if document-level
                                     avg confidence < threshold.

        Returns:
            {text, min_confidence, avg_confidence, page_count, word_count}

        Raises:
            LowConfidenceError: if average confidence is below threshold and
                                raise_on_low_confidence is True.
            ImportError:        if paddleocr is not installed.
        """
        return run_ocr(
            page_images=page_images,
            form_type=form_type,
            raise_on_low_confidence=raise_on_low_confidence,
        )

    # Re-export the exception so callers don't need to import ocr_engine directly
    LowConfidenceError = LowConfidenceError
