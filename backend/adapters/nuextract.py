"""
backend/adapters/nuextract.py
==============================
Adapter wrapping nuextract_normalizer.py for future extraction as the
Extraction Engine microservice.

The NuMind SDK call signature is an external contract — do not change it.
This adapter wraps the call so the rest of the service never imports the
SDK directly; only the adapter does.
"""

from backend.extraction.nuextract_normalizer import normalize as _normalize


class NuExtractAdapter:
    """
    Wraps nuextract_normalizer.normalize() for Extraction Engine extraction.

    The underlying SDK call is immutable.  Any changes to normalisation
    behaviour should be implemented in the adapter layer, not in
    nuextract_normalizer.py.
    """

    def normalize(
        self,
        schema: dict,
        input_text: str = None,
        input_file: bytes = None,
        instructions: str = "",
    ) -> dict:
        """
        Normalise raw text or a file into a structured typed dict via NuExtract.

        Args:
            schema:       The strict typed JSON schema for the form type.
            input_text:   Markdown string (digital or OCR path).
            input_file:   Raw PDF/image bytes (vision fallback path).
            instructions: Optional extraction guidance for the model.

        Returns:
            Clean typed dict with all fields normalised to schema spec.
        """
        return _normalize(
            schema=schema,
            input_text=input_text,
            input_file=input_file,
            instructions=instructions,
        )
