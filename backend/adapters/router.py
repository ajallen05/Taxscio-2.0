"""
backend/adapters/router.py
==========================
Adapter wrapping pdf_router.py and preprocessor.py for future extraction as
the Document Validator microservice.

RouterAdapter owns the detect → route → preprocess responsibility.
"""

from backend.ingestion.pdf_router import (
    route_pdf,
    route_pdf_with_preprocessing,
    route_image,
    detect_form_boundaries,
)


class RouterAdapter:
    """Wraps pdf_router.py for Document Validator extraction."""

    def route(self, pdf_bytes: bytes, preprocess: bool = True) -> tuple:
        """
        Route a document to the correct extraction path.
        Detects if bytes represent an image (PNG/JPEG) instead of PDF.

        Args:
            pdf_bytes:  Raw document bytes.
            preprocess: If True (default), apply OpenCV preprocessing to
                        scanned pages before returning.

        Returns:
            (pdf_type: str, content: str | list[str])
            pdf_type is "digital" (Markdown string) or "scanned" (base64 list).
        """
        # Detect magic bytes for common image formats
        if pdf_bytes.startswith(b'\xff\xd8') or pdf_bytes.startswith(b'\x89PNG'):
            return self.route_image(pdf_bytes)
            
        if preprocess:
            return route_pdf_with_preprocessing(pdf_bytes)
        return route_pdf(pdf_bytes)

    def route_image(self, image_bytes: bytes, file_ext: str = "png") -> tuple:
        """Route a standalone image file."""
        return route_image(image_bytes, file_ext=file_ext)

    def detect_boundaries(self, pdf_bytes: bytes) -> list:
        """
        Detect multiple IRS forms within a single PDF.

        Returns list of (start_page, end_page) tuples (0-indexed, inclusive).
        Useful for multi-form PDFs (e.g. W-2 + 1099-NEC in one file).
        """
        return detect_form_boundaries(pdf_bytes)
