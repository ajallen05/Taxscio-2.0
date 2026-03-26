"""
config.py
=========
Central configuration for the Taxscio monolith.

All hardcoded constants that were previously scattered across five separate
files now live here so they can be changed in one place and so they are
ready to move to environment variables when services are extracted.

Usage:
    from backend.config import config
    threshold = config.ocr_confidence_threshold

NOTE: engine.py (immutable) defines its own copy of the shared numeric
constants. auto_fixer.py was updated to import from here instead.
"""

import os
from dataclasses import dataclass, field


def _project_root() -> str:
    """Return the project root (parent of backend/)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class Config:
    # ── API keys ──────────────────────────────────────────────────────────────
    numind_api_key: str = field(
        default_factory=lambda: os.environ.get("NUMIND_API_KEY", "")
    )
    openrouter_api_key: str = field(
        default_factory=lambda: os.environ.get("OPENROUTER_API_KEY", "")
    )

    # ── OCR ───────────────────────────────────────────────────────────────────
    # Minimum average page confidence before falling back to NuExtract Vision.
    # Mirrors OCR_CONFIDENCE_THRESHOLD in engine.py (0.80).
    ocr_confidence_threshold: float = field(
        default_factory=lambda: float(
            os.environ.get("OCR_CONFIDENCE_THRESHOLD", "0.80")
        )
    )
    # Y-axis pixel tolerance for grouping OCR words into the same row.
    row_y_tolerance: int = field(
        default_factory=lambda: int(os.environ.get("ROW_Y_TOLERANCE", "8"))
    )
    # Label written to ocr_source when NuExtract Vision handles a scanned doc.
    # Must be one of: "paddleocr" | "qwen_fallback" | "pymupdf4llm"
    ocr_fallback_source_label: str = "qwen_fallback"

    # ── Image preprocessing ────────────────────────────────────────────────────
    preprocessor_target_width_px: int = field(
        default_factory=lambda: int(
            os.environ.get("PREPROCESSOR_TARGET_WIDTH_PX", "2550")
        )
    )
    preprocessor_min_width_px: int = field(
        default_factory=lambda: int(
            os.environ.get("PREPROCESSOR_MIN_WIDTH_PX", "1700")
        )
    )

    # ── Gate ──────────────────────────────────────────────────────────────────
    # Score threshold (0–100) for IRS form detection.
    gate_threshold: int = field(
        default_factory=lambda: int(os.environ.get("GATE_THRESHOLD", "30"))
    )

    # ── Validation / IRS math ─────────────────────────────────────────────────
    # These mirror the constants in engine.py (immutable).
    # auto_fixer.py imports from here instead of defining its own copies.
    ss_rate: float = 0.062
    medicare_rate: float = 0.0145
    math_tolerance: float = 1.00

    # ── Schemas ───────────────────────────────────────────────────────────────
    schemas_dir: str = field(
        default_factory=lambda: os.environ.get(
            "SCHEMAS_DIR",
            os.path.join(_project_root(), "backend", "schemas"),
        )
    )

    # ── Confidence review thresholds ──────────────────────────────────────────
    field_review_threshold: float = 0.75   # fields below this need human review
    doc_review_threshold: float = 0.85     # docs below this flagged needs_review


config = Config()
