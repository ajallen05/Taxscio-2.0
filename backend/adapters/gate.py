"""
backend/adapters/gate.py
========================
Adapter wrapping gate.py for future extraction as the Document Validator
microservice.

The underlying functions are unchanged.  This class is the seam — when the
Document Validator is extracted, its service.py will instantiate GateAdapter
and call its methods instead of importing gate functions directly.
"""

from backend.ingestion.gate import (
    verify_is_tax_form_from_pdf,
    verify_is_tax_form_from_text,
    verify_is_tax_form,
)


class GateAdapter:
    """Wraps gate.py IRS form detection for Document Validator extraction."""

    def verify_pdf(self, pdf_bytes: bytes) -> dict:
        """
        Determine whether a PDF is an IRS tax form using embedded text.

        Returns:
            {is_tax_form, form_type, tax_year, omb_number, score,
             signals_found, rejection_reason}
        """
        return verify_is_tax_form_from_pdf(pdf_bytes)

    def verify_text(self, text: str) -> dict:
        """
        Determine whether extracted text belongs to an IRS tax form.

        Used after OCR on scanned documents.
        """
        return verify_is_tax_form_from_text(text)

    def verify_source(self, document_source: dict) -> dict:
        """
        Legacy compatibility wrapper.

        Args:
            document_source: {"type": "text"|"image", "content": str}
        """
        return verify_is_tax_form(document_source)
