# ══════════════════════════════════════════════════════════════
#  Taxscio API Gateway — FastAPI
#  uvicorn backend.main:app --host 0.0.0.0 --port 8000
# ══════════════════════════════════════════════════════════════

import asyncio
import json
import os
import sys
import traceback
import time
import logging
import secrets
import base64
from datetime import datetime, timedelta, timezone
from typing import Any

# ── Path bootstrap ─────────────────────────────────────────────────────────────
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dotenv import load_dotenv
# Load env vars from backend/.env explicitly so DATABASE_URL is always found
# regardless of where the server is launched from.
_backend_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_backend_dir, ".env"))
# Also try project root .env as fallback
load_dotenv(os.path.join(_project_root, ".env"))

from fastapi import FastAPI, Header, UploadFile, File, Form, Request, Cookie, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from numind import NuMind

# ── Adapters (strangler fig seams) ────────────────────────────────────────────
from backend.adapters.extraction_engine import ExtractionEngineAdapter, ExtractionFailedError
from backend.adapters.data_integrity_engine import DataIntegrityEngineAdapter
from backend.adapters.export_formatter import ExportFormatterAdapter
from backend.adapters.document_validator import DocumentValidatorAdapter
from backend.utils.data import normalize_form_type
from backend.utils.schemas import get_schema, get_available_forms

# ── Ledger integration ────────────────────────────────────────────────────────
from backend.ledger.database import init_db, SessionLocal
from backend.ledger.schemas import DocumentCreate as LedgerDocumentCreate
from backend.ledger.services import create_document as ledger_create_document

# ── Client Database integration ───────────────────────────────────────────────
from backend.client_database.database import init_db as client_init_db
from backend.client_database.routes import router as client_router

def _ledger_get_session():
    if SessionLocal is not None:
        return SessionLocal()
    return None

from backend.ledger.routes import ledger_bp
from flask import Flask
from fastapi.middleware.wsgi import WSGIMiddleware

flask_app = Flask(__name__)
flask_app.register_blueprint(ledger_bp)

_extraction_engine = ExtractionEngineAdapter()
_data_integrity = DataIntegrityEngineAdapter()
_export_formatter = ExportFormatterAdapter()
_doc_validator = DocumentValidatorAdapter()

# ── NuMind client ─────────────────────────────────────────────────────────────
API_KEY = os.environ.get("NUMIND_API_KEY", "")
if not API_KEY:
    raise RuntimeError("NUMIND_API_KEY not set.")
client = NuMind(api_key=API_KEY)

log = logging.getLogger("Taxscio.gateway")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Taxscio API Gateway",
    version="1.0.0",
    description="Tax document extraction and validation gateway",
)

# ── Ledger router ─────────────────────────────────────────────────────────────
app.mount("/ledger", WSGIMiddleware(flask_app))

# ── Client Database router ────────────────────────────────────────────────────
app.include_router(client_router)


@app.on_event("startup")
def _startup():
    """Initialise the ledger database tables on server start."""
    try:
        init_db()
        log.info("Ledger DB initialised (tables created if missing).")
    except Exception as exc:
        log.warning("Ledger DB init skipped (no DATABASE_URL?): %s", exc)
    try:
        client_init_db()
        log.info("Client DB initialised (tables created if missing).")
    except Exception as exc:
        log.warning("Client DB init skipped: %s", exc)

# ── CORS — must be added before routes ────────────────────────────────────────
_allowed_origins = [
    "http://localhost",
    "http://localhost:80",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    "null",  # file:// protocol
]
_ec2_origin = os.environ.get("EC2_ORIGIN")
if _ec2_origin:
    _allowed_origins.append(_ec2_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Constants ─────────────────────────────────────────────────────────────────

DETECTION_TEMPLATE = {
    "form_type": "verbatim-string",
    "tax_year":  "integer",
    "omb_number": "verbatim-string",
}

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}

log.info("Taxscio gateway initialised — FastAPI + dual routes.")


# ── Ledger auto-submit helper ─────────────────────────────────────────────────

def _submit_to_ledger(
    filename: str,
    form_type: str,
    confidence_score: float | None,
    context: dict | None = None,
    client_name_override: str | None = None,
    extraction_data: dict | None = None,
    validation_data: dict | None = None,
    stage: str = "AI Processing",
    status: str = "EXTRACTED",
) -> str | None:
    """
    Persist an AI-processing ledger record after a successful extraction.
    Returns doc_id on success, else None.
    """
    db = _ledger_get_session()
    if db is None:
        log.warning("Ledger DB not configured — _submit_to_ledger skipped. "
                    "Check DATABASE_URL in backend/.env")
        return
    ctx = context or {}
    
    def find_name(d):
        if not isinstance(d, dict):
            return None
        # Priority 1: High-confidence CLIENT/TAXPAYER fields
        client_suffixes = [
            "name_on_return", "taxpayer_name", "employee_name", "partner_name", 
            "beneficiary_name", "shareholder_name", "client_name", "payee_name",
            "filer_name", "recipient_name", "transferor_name"
        ]
        # Priority 2: Generic or secondary names (entities, companies, etc.)
        entity_suffixes = [
             "business_name", "company_name", "entity_name", "employer_name", 
             "payer_name", "trustee_or_payer_name"
        ]
        
        # Check client suffixes first
        for key, val in d.items():
            if isinstance(val, str) and val.strip():
                k = key.lower()
                if k == "name" or any(k.endswith(s) for s in client_suffixes):
                    return val.strip()
        
        # Check combined first/last fields
        for prefix in ["taxpayer", "employee", "client"]:
            first, last = None, None
            for k in d.keys():
                if k.lower().endswith(f"{prefix}_first_name"): first = d[k]
                if k.lower().endswith(f"{prefix}_last_name"): last = d[k]
            if isinstance(first, str) and isinstance(last, str) and first.strip() and last.strip():
                return f"{first.strip()} {last.strip()}"

        # Check entity/secondary suffixes last
        for key, val in d.items():
            if isinstance(val, str) and val.strip():
                k = key.lower()
                if any(k.endswith(s) for s in entity_suffixes):
                    return val.strip()
                
        for v in d.values():
            if isinstance(v, dict):
                res = find_name(v)
                if res: return res
        return None

    extracted_name = None
    if extraction_data:
        extracted_name = find_name(extraction_data)

    client_name = client_name_override or extracted_name or ctx.get("client_name") or filename
    tax_year_raw = ctx.get("tax_year")
    try:
        tax_year = int(tax_year_raw) if tax_year_raw else datetime.now(timezone.utc).year
    except (TypeError, ValueError):
        tax_year = datetime.now(timezone.utc).year

    data = LedgerDocumentCreate(
        client_name=client_name,
        document_type=form_type or "Unknown",
        provider="Taxscio AI",
        description=f"Auto-extracted: {filename}",
        source=filename,
        tax_year=tax_year,
        stage=stage,
        status=status,
        confidence_score=confidence_score,
        cpa=ctx.get("cpa"),
        due_date=ctx.get("due_date"),
        extraction_data=extraction_data,
        validation_data=validation_data,
    )
    try:
        doc_id = ledger_create_document(db, data)
        log.info("Ledger auto-submit OK: document_id=%s form=%s client=%s",
                 doc_id, form_type, client_name)
        return doc_id
    except Exception as exc:
        db.rollback()
        log.warning("Ledger auto-submit FAILED: %s", exc)
        return None
    finally:
        db.close()

def _get_escalated_exceptions(document_id: str) -> list[dict]:
    """Fetch escalated exceptions from the ledger audit trail to silence them."""
    db = _ledger_get_session()
    if db is None or not document_id:
        return []
    try:
        from backend.ledger.models import Ledger
        ledger = db.query(Ledger).filter(Ledger.document_id == document_id).first()
        if not ledger or not ledger.audit_trail:
            return []
        escalated = []
        for item in ledger.audit_trail:
            if item.get("type") == "exception_escalated":
                escalated.append({
                    "code": item.get("exception_code"),
                    "field": item.get("exception_field")
                })
        return escalated
    except Exception as exc:
        log.warning("Failed to fetch escalated exceptions: %s", exc)
        return []
    finally:
        db.close()


# ── Event / Agent logging ──────────────────────────────────────────────────────

_event_log: list[dict[str, Any]] = []
_agent_log: list[dict[str, Any]] = []
_log_lock = asyncio.Lock()


async def log_event(event_type: str, detail: str, session_id: str | None = None) -> None:
    async with _log_lock:
        _event_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "detail": detail,
            "session_id": session_id,
        })


async def log_agent(action: str, detail: str, session_id: str | None = None) -> None:
    async with _log_lock:
        _agent_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "detail": detail,
            "session_id": session_id,
        })


# ── Status vocabulary mapping ────────────────────────────────────────────────

STATUS_MAP = {
    "TAX_FORM_IDENTIFIED": "processing",
    "EXTRACTION_COMPLETE": "processing",
    "EXCEPTIONS_FOUND": "exception",
    "NO_EXCEPTIONS": "approved",
    "NEEDS_REVIEW": "review",
    "FIXES_APPLIED": "processing",
    "EXPORT_READY": "approved",
    "ERROR": "error",
}

# ── Session management (Group B routes only) ──────────────────────────────────

SESSIONS: dict[str, dict[str, Any]] = {}
COOKIE_NAME = "taxio_session"
SESSION_TIMEOUT_MINUTES = 30


def _create_session() -> tuple[str, dict[str, Any]]:
    sid = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    session: dict[str, Any] = {
        "session_id": sid,
        "raw_text": None,
        "form_type": None,
        "document_type": None,
        "pdf_type": None,
        "extracted_fields": None,
        "current_exceptions": None,
        "correction_history": [],
        "pipeline_stage": "created",
        "ui_status": "processing",
        "client_name": None,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=SESSION_TIMEOUT_MINUTES)).isoformat(),
    }
    SESSIONS[sid] = session
    return sid, session


def _resolve_session_id(
    cookie_sid: str | None = None,
    header_sid: str | None = None,
) -> str | None:
    """Dual session lookup: cookie first, then X-Session-ID header."""
    return cookie_sid or header_sid


def _get_session(sid: str | None) -> dict[str, Any] | None:
    if not sid or sid not in SESSIONS:
        return None
    session = SESSIONS[sid]
    expires = datetime.fromisoformat(session["expires_at"])
    if datetime.now(timezone.utc) > expires:
        del SESSIONS[sid]
        return None
    return session


def _taxio_response(
    data: Any = None,
    error: Any = None,
    request_id: str = "",
    ok: bool = True,
) -> dict[str, Any]:
    """Build the TaxioResponse envelope for Group B routes."""
    return {
        "ok": ok,
        "service": "gateway",
        "version": "1.0.0",
        "request_id": request_id,
        "error": error,
        "data": data,
    }


def _check_file_ext(filename: str) -> str | None:
    """Return extension if supported, else None."""
    ext = os.path.splitext(filename)[1].lower()
    return ext if ext in SUPPORTED_EXTENSIONS else None


# ── Request models (Group A JSON routes) ──────────────────────────────────────

class ValidateBody(BaseModel):
    model_config = {"extra": "allow"}
    form_type: str | None = None
    data: Any = None
    pdf_type: str = "digital"
    context: dict[str, Any] = {}
    human_verified_fields: list[str] = []
    filename: str | None = None


class ApplyFixesBody(BaseModel):
    model_config = {"extra": "allow"}
    form_type: str | None = None
    data: Any = None
    fixes: Any = []
    pdf_type: str = "scanned"
    human_verified_fields: list[str] = []
    context: dict[str, Any] = {}


class RevalidateBody(BaseModel):
    model_config = {"extra": "allow"}
    form_type: str | None = None
    data: Any = None
    pdf_type: str = "scanned"
    context: dict[str, Any] | None = {}
    human_verified_fields: list[str] = []


# ── Request models (Group B JSON routes) ──────────────────────────────────────

class CorrectBody(BaseModel):
    model_config = {"extra": "allow"}
    corrections: list[dict[str, Any]] = []
    human_verified_fields: list[str] = []


class ExportQuery(BaseModel):
    model_config = {"extra": "allow"}
    format: str = "json"


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE GROUP A — Legacy (current frontend, stateless, FLAT responses)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {
        "status":     "ready",
        "backend":    "nuextract.ai API",
        "model":      "NuExtract 2.0 PRO",
        "model_size": "PRO",
    }


@app.get("/forms")
def get_forms_route():
    return {"forms": get_available_forms()}


@app.post("/detect")
def detect(file: UploadFile = File(...)):
    from backend.ingestion.pdf_router import route_pdf, route_image
    from backend.extraction.nuextract_normalizer import normalize

    try:
        filename = (file.filename or "").lower()
        file_bytes = file.file.read()
        extension = os.path.splitext(filename)[1].lower()

        if not _check_file_ext(filename):
            return JSONResponse(
                {"error": "Unsupported file type. Use PDF, PNG, JPG, or WebP."},
                status_code=400,
            )

        # STAGE 1: Route
        if filename.endswith(".pdf"):
            pdf_type, content = route_pdf(file_bytes)
        else:
            pdf_type, content = route_image(file_bytes, file_ext=extension)

        # STAGE 2: Detect form type via NuExtract Vision
        detected_data = normalize(
            schema=DETECTION_TEMPLATE,
            input_file=file_bytes,
            instructions="Identify the IRS form type (e.g., W-2, 1099-INT), tax year, and OMB number.",
        )

        if "form_type" in detected_data:
            detected_data["form_type"] = normalize_form_type(detected_data["form_type"])

        # Page count
        import fitz as _fitz
        try:
            _doc = _fitz.open(stream=file_bytes, filetype="pdf")
            pages_processed = _doc.page_count
            _doc.close()
        except Exception:
            pages_processed = len(content) if isinstance(content, list) else 1

        return {
            "detected":        detected_data,
            "pages_processed": pages_processed,
        }

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            {"error": str(e), "trace": traceback.format_exc()},
            status_code=500,
        )


@app.post("/extract")
def extract(
    req: Request,
    file: UploadFile = File(...),
    form_type: str = Form(""),
    fields_only: str = Form("false"),
    context: str = Form(""),
):
    try:
        form_type = form_type.strip()
        is_fields_only = fields_only.lower() == "true"

        if not form_type:
            return JSONResponse(
                {"error": "Missing required field 'form_type'."},
                status_code=400,
            )

        schema = get_schema(form_type)
        if not schema:
            return JSONResponse(
                {
                    "error":     f"Unknown form_type '{form_type}'. Could not find matching schema.",
                    "supported": get_available_forms(),
                },
                status_code=400,
            )

        filename = (file.filename or "").lower()
        file_bytes = file.file.read()

        if not _check_file_ext(filename):
            return JSONResponse(
                {"error": "Unsupported file type. Use PDF, PNG, JPG, or WebP."},
                status_code=400,
            )

        # Parse optional context
        context_dict: dict[str, Any] = {}
        if context:
            try:
                context_dict = json.loads(context)
            except Exception as ctx_err:
                log.warning("Failed to parse context JSON: %s", ctx_err)

        request_id = req.headers.get("X-Request-ID", "")

        # ── STAGE 1: Document Validation (gate + pdf_type detection) ──────────
        try:
            t0 = time.time()
            gate_result = _doc_validator.validate_pdf(
                file_bytes,
                request_id=request_id,
            )
            validation_latency = round(time.time() - t0, 3)
        except Exception as e:
            traceback.print_exc()
            return JSONResponse(
                {"error": f"Step 1 (Document Validator) failed: {str(e)}"},
                status_code=500,
            )

        if not gate_result["is_valid_tax_form"] and gate_result.get("confidence_score") != -1:
            return JSONResponse(
                {
                    "error":   "Document rejected: not an IRS tax form.",
                    "reason":  gate_result.get("rejection_reason"),
                    "score":   gate_result.get("confidence_score"),
                    "signals": gate_result.get("signals_found"),
                },
                status_code=422,
            )

        pdf_type = gate_result.get("pdf_type")

        # ── STAGE 2+3: Extraction Engine (OCR + NuExtract) ───────────────────
        try:
            input_text, normalized, ocr_source, extraction_latency = \
                _extraction_engine.extract_for_pipeline(
                    document_bytes=file_bytes,
                    form_type=form_type,
                    pdf_type=pdf_type,
                    request_id=request_id,
                )
        except ExtractionFailedError as e:
            return JSONResponse(
                {"error": e.message, "error_code": e.code, "form_type": form_type},
                status_code=500,
            )
        except Exception as e:
            traceback.print_exc()
            return JSONResponse(
                {"error": f"Step 2+3 (Extraction Engine) failed: {str(e)}"},
                status_code=500,
            )

        log.debug(
            "Extracted text source=%s preview=%s",
            ocr_source,
            str(input_text)[:200] if input_text else "VISION FALLBACK",
        )

        # ── Latency bundle ───────────────────────────────────────────────────
        latency = {
            "validation_seconds":  validation_latency,
            "extraction_seconds":  extraction_latency,
            "total_seconds":       round(validation_latency + extraction_latency, 2),
        }

        # ── OPTIONAL: fields_only — skip validation (Pass 1 of batch loop) ──
        if is_fields_only:
            return {
                "form_type":           form_type,
                "pdf_type":            pdf_type,
                "ocr_source":          ocr_source,
                "latency":             latency,
                "data":                normalized,
                "raw_extracted_text":  input_text,
                "raw_normalized_json": normalized,
            }

        # ── STAGE 4: Data Integrity Engine ───────────────────────────────────
        integrity_result = _data_integrity.validate(
            form_type=form_type,
            extracted_fields=normalized,
            context=context_dict,
            pdf_type=pdf_type,
            request_id=request_id,
        )
        integrity_data = integrity_result["data"]

        pipeline = {
            "val_result": {
                "exceptions": integrity_data.get("exceptions", []),
                "errors":     integrity_data.get("errors", []),
                "confidence": integrity_data.get("confidence", 1.0),
                "summary":    integrity_data.get("summary_validation") or {},
            },
            "fixable_exceptions": integrity_data.get("fixable_exceptions", []),
            "review_exceptions":  integrity_data.get("review_exceptions", []),
            "confidence_result": {
                "field_scores":        integrity_data.get("field_confidence", {}),
                "document_confidence": integrity_data.get("document_confidence", 1.0),
                "needs_review":        integrity_data.get("needs_review", False),
                "review_fields":       integrity_data.get("review_fields", []),
            },
        }

        # ── STAGE 5: Export Formatter ────────────────────────────────────────
        final_response = _export_formatter.format_extraction(
            form_type=form_type,
            validated_data=normalized,
            pipeline_result=pipeline,
            pdf_type=pdf_type,
            ocr_source=ocr_source,
            latency=latency,
            raw_extracted_text=input_text,
            correction_log=[],
            human_verified_fields=[],
        )

        log.info(
            "Extract complete: form=%s pdf=%s exceptions=%d doc_confidence=%.3f",
            form_type, pdf_type,
            len(final_response["exceptions"]),
            final_response["document_confidence"],
        )

        # ── Auto-submit ledger record ─────────────────────────────────────────
        doc_id = _submit_to_ledger(
            filename=file.filename or "unknown",
            form_type=form_type,
            confidence_score=final_response.get("document_confidence"),
            context=context_dict,
            extraction_data=normalized,
            validation_data=integrity_data,
        )
        if doc_id:
            final_response["document_id"] = doc_id

        # Debug dump to disk
        try:
            with open("latest_response.json", "w", encoding="utf-8") as dr:
                json.dump(final_response, dr, indent=2)
        except Exception:
            pass

        return final_response

    except Exception as e:
        return JSONResponse(
            {"error": str(e), "trace": traceback.format_exc()},
            status_code=500,
        )


@app.post("/validate")
def validate_route(req: Request, body: ValidateBody):
    try:
        form_type = (body.form_type or "").strip()
        if not form_type:
            return JSONResponse(
                {"error": "Missing required field 'form_type'."},
                status_code=400,
            )
        if not isinstance(body.data, dict):
            return JSONResponse(
                {"error": "'data' must be a JSON object."},
                status_code=400,
            )

        result = _data_integrity.validate(
            form_type=form_type,
            extracted_fields=body.data,
            context=body.context,
            pdf_type=body.pdf_type,
            human_verified_fields=body.human_verified_fields,
            request_id=req.headers.get("X-Request-ID"),
        )
        integrity_data = result["data"]

        doc_id = None
        if body.filename:
            doc_id = _submit_to_ledger(
                filename=body.filename,
                form_type=form_type,
                confidence_score=integrity_data.get("document_confidence", 1.0),
                context=body.context,
                extraction_data=body.data,
                validation_data=integrity_data,
                stage="Validation",
                status="VALIDATED"
            )

        return {
            "form_type":             form_type,
            "document_id":          doc_id,
            "pdf_type":              body.pdf_type,
            "confidence":            integrity_data.get("confidence", 1.0),
            "errors":                integrity_data.get("errors", []),
            "exceptions":            integrity_data.get("exceptions", []),
            "summary":               integrity_data.get("summary_validation") or {},
            "fixable_exceptions":    integrity_data.get("fixable_exceptions", []),
            "review_exceptions":     integrity_data.get("review_exceptions", []),
            "data":                  body.data,
            "field_confidence":      integrity_data.get("field_confidence", {}),
            "document_confidence":   integrity_data.get("document_confidence", 1.0),
            "needs_review":          integrity_data.get("needs_review", False),
            "review_fields":         integrity_data.get("review_fields", []),
            "human_verified_fields": integrity_data.get("human_verified_fields", body.human_verified_fields),
        }

    except Exception as e:
        return JSONResponse(
            {"error": str(e), "trace": traceback.format_exc()},
            status_code=500,
        )


@app.post("/apply-fixes")
def apply_fixes_route(req: Request, body: ApplyFixesBody):
    try:
        form_type = (body.form_type or "").strip()
        if not form_type:
            return JSONResponse(
                {"error": "Missing required field 'form_type'."},
                status_code=400,
            )
        if not isinstance(body.data, dict):
            return JSONResponse(
                {"error": "'data' must be a JSON object."},
                status_code=400,
            )
        if not isinstance(body.fixes, list):
            return JSONResponse(
                {"error": "'fixes' must be a JSON array."},
                status_code=400,
            )

        result = _data_integrity.apply_fixes(
            form_type=form_type,
            extracted_fields=body.data,
            fixes=body.fixes,
            context=body.context,
            pdf_type=body.pdf_type,
            human_verified_fields=body.human_verified_fields,
            request_id=req.headers.get("X-Request-ID"),
        )
        integrity_data = result["data"]
        
        doc_id = None
        if body.context.get("filename"):
            doc_id = _submit_to_ledger(
                filename=body.context.get("filename"),
                form_type=form_type,
                confidence_score=integrity_data.get("document_confidence", 1.0),
                context=body.context,
                extraction_data=integrity_data.get("patched_fields") or body.data,
                validation_data=integrity_data,
                stage="Correction",
                status="VALIDATED"
            )

        return {
            "form_type":             form_type,
            "document_id":          doc_id,
            "pdf_type":              body.pdf_type,
            "confidence":            integrity_data.get("confidence", 1.0),
            "errors":                integrity_data.get("errors", []),
            "exceptions":            integrity_data.get("exceptions", []),
            "summary":               integrity_data.get("summary_validation") or {},
            "fixable_exceptions":    integrity_data.get("fixable_exceptions", []),
            "review_exceptions":     integrity_data.get("review_exceptions", []),
            "data":                  integrity_data.get("patched_fields") or body.data,
            "field_confidence":      integrity_data.get("field_confidence", {}),
            "document_confidence":   integrity_data.get("document_confidence", 1.0),
            "needs_review":          integrity_data.get("needs_review", False),
            "review_fields":         integrity_data.get("review_fields", []),
            "human_verified_fields": integrity_data.get("human_verified_fields", body.human_verified_fields),
            "fixes_applied":         integrity_data.get("fixes_applied", len(body.fixes)),
        }

    except Exception as e:
        return JSONResponse(
            {"error": str(e), "trace": traceback.format_exc()},
            status_code=500,
        )


@app.post("/revalidate")
def revalidate_route(req: Request, body: RevalidateBody):
    try:
        form_type = (body.form_type or "").strip()
        if not form_type:
            return JSONResponse(
                {"error": "Missing 'form_type'."},
                status_code=400,
            )
        if not isinstance(body.data, dict):
            return JSONResponse(
                {"error": "'data' must be a JSON object."},
                status_code=400,
            )

        result = _data_integrity.revalidate(
            form_type=form_type,
            extracted_fields=body.data,
            context=body.context or {},
            pdf_type=body.pdf_type,
            human_verified_fields=body.human_verified_fields,
            request_id=req.headers.get("X-Request-ID"),
        )
        integrity_data = result["data"]
        
        doc_id = None
        if body.context.get("filename"):
            doc_id = _submit_to_ledger(
                filename=body.context.get("filename"),
                form_type=form_type,
                confidence_score=integrity_data.get("document_confidence", 1.0),
                context=body.context,
                extraction_data=body.data,
                validation_data=integrity_data,
                stage="Re-validation",
                status="VALIDATED"
            )

        return {
            "form_type":             form_type,
            "document_id":          doc_id,
            "pdf_type":              body.pdf_type,
            "confidence":            integrity_data.get("confidence", 1.0),
            "errors":                integrity_data.get("errors", []),
            "exceptions":            integrity_data.get("exceptions", []),
            "summary":               integrity_data.get("summary_validation") or {},
            "fixable_exceptions":    integrity_data.get("fixable_exceptions", []),
            "review_exceptions":     integrity_data.get("review_exceptions", []),
            "data":                  body.data,
            "field_confidence":      integrity_data.get("field_confidence", {}),
            "document_confidence":   integrity_data.get("document_confidence", 1.0),
            "needs_review":          integrity_data.get("needs_review", False),
            "review_fields":         integrity_data.get("review_fields", []),
            "human_verified_fields": integrity_data.get("human_verified_fields", body.human_verified_fields),
        }

    except Exception as e:
        return JSONResponse(
            {"error": str(e), "trace": traceback.format_exc()},
            status_code=500,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE GROUP B — New API (session-based, future frontend)
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/upload")
async def api_upload(response: Response, file: UploadFile = File(...)):
    """Upload a document, validate via gate, detect form type, create session."""
    from backend.extraction.nuextract_normalizer import normalize

    try:
        filename = (file.filename or "").lower()
        file_bytes = file.file.read()

        if not _check_file_ext(filename):
            return JSONResponse(
                _taxio_response(
                    error={"code": "UNSUPPORTED_FILE", "message": "Use PDF, PNG, JPG, or WebP."},
                    ok=False,
                ),
                status_code=400,
            )

        gate_result = _doc_validator.validate_upload(
            file_bytes=file_bytes,
            filename=filename,
            source="platform_ui"
        )

        if not gate_result["is_valid_tax_form"] and gate_result.get("confidence_score") != -1:
            return JSONResponse(
                _taxio_response(
                    error={
                        "code": "NOT_TAX_FORM",
                        "message": "Document rejected: not an IRS tax form.",
                        "details": {
                            "reason": gate_result.get("rejection_reason"),
                            "score": gate_result.get("confidence_score"),
                        },
                    },
                    ok=False,
                ),
                status_code=422,
            )

        detected = normalize(
            schema=DETECTION_TEMPLATE,
            input_file=file_bytes,
            instructions="Identify the IRS form type (e.g., W-2, 1099-INT), tax year, and OMB number.",
        )
        if "form_type" in detected:
            detected["form_type"] = normalize_form_type(detected["form_type"])

        sid, session = _create_session()
        session["_document_bytes_b64"] = base64.b64encode(file_bytes).decode("utf-8")
        session["form_type"] = detected.get("form_type")
        session["pdf_type"] = gate_result.get("pdf_type")
        session["document_type"] = gate_result.get("pdf_type")
        session["raw_text"] = gate_result.get("raw_text")
        session["filename"] = filename
        session["pipeline_stage"] = "uploaded"
        session["ui_status"] = STATUS_MAP.get("TAX_FORM_IDENTIFIED", "processing")

        response.set_cookie(
            COOKIE_NAME, sid,
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=SESSION_TIMEOUT_MINUTES * 60,
        )

        await log_event("UPLOAD", f"form={detected.get('form_type')} pdf_type={gate_result.get('pdf_type')}", sid)

        return _taxio_response(
            data={
                "session_id": sid,
                "detected": detected,
                "pdf_type": gate_result.get("pdf_type"),
                "is_valid_tax_form": gate_result["is_valid_tax_form"],
                "pipeline_stage": "uploaded",
            },
            request_id=sid,
        )

    except Exception as e:
        return JSONResponse(
            _taxio_response(
                error={"code": "UPLOAD_FAILED", "message": str(e)},
                ok=False,
            ),
            status_code=500,
        )


@app.post("/api/extract")
async def api_extract(
    taxio_session: str | None = Cookie(None),
    x_session_id: str | None = Header(None),
):
    """Extract fields from the uploaded document stored in session."""
    try:
        sid = _resolve_session_id(taxio_session, x_session_id)
        session = _get_session(sid)
        if not session:
            return JSONResponse(
                _taxio_response(
                    error={"code": "NO_SESSION", "message": "No active session. Upload a document first."},
                    ok=False,
                ),
                status_code=401,
            )

        if session["pipeline_stage"] not in ("uploaded", "extracted"):
            return JSONResponse(
                _taxio_response(
                    error={"code": "INVALID_STAGE", "message": f"Cannot extract at stage '{session['pipeline_stage']}'."},
                    ok=False,
                ),
                status_code=400,
            )

        form_type = session.get("form_type")
        if not form_type:
            return JSONResponse(
                _taxio_response(
                    error={"code": "NO_FORM_TYPE", "message": "No form type detected. Re-upload the document."},
                    ok=False,
                ),
                status_code=400,
            )

        pdf_type = session.get("pdf_type")
        raw_text = session.get("raw_text")
        if raw_text:
            input_text, normalized, ocr_source, extraction_latency = \
                _extraction_engine.extract_from_text(
                    raw_text=raw_text,
                    form_type=form_type,
                )
        else:
            doc_bytes = base64.b64decode(session["_document_bytes_b64"])
            input_text, normalized, ocr_source, extraction_latency = \
                _extraction_engine.extract_for_pipeline(
                    document_bytes=doc_bytes,
                    form_type=form_type,
                    pdf_type=pdf_type,
                )

        session["raw_text"] = input_text or raw_text
        session["extracted_fields"] = normalized

        integrity_result = _data_integrity.validate(
            form_type=form_type,
            extracted_fields=normalized,
            pdf_type=pdf_type,
        )
        integrity_data = integrity_result["data"]

        exceptions = integrity_data.get("exceptions", [])
        session["current_exceptions"] = exceptions
        session["pipeline_stage"] = "extracted"

        if exceptions:
            session["ui_status"] = STATUS_MAP.get("EXCEPTIONS_FOUND", "exception")
        else:
            session["ui_status"] = STATUS_MAP.get("NO_EXCEPTIONS", "approved")

        await log_event("EXTRACT", f"form={form_type} fields={len(normalized)} ocr={ocr_source}", session["session_id"])

        # ── Auto-submit ledger record ─────────────────────────────────────────
        doc_id = await asyncio.to_thread(
            _submit_to_ledger,
            filename=session.get("filename", "unknown_from_session"),
            form_type=form_type,
            confidence_score=integrity_data.get("document_confidence", 1.0),
            context={"tax_year": datetime.now().year},
            extraction_data=normalized,
            validation_data=integrity_data,
        )
        if doc_id:
            session["document_id"] = doc_id

        return _taxio_response(
            data={
                "form_type": form_type,
                "document_id": doc_id,
                "pdf_type": pdf_type,
                "ocr_source": ocr_source,
                "extracted_fields": normalized,
                "exceptions": exceptions,
                "fixable_exceptions": integrity_data.get("fixable_exceptions", []),
                "review_exceptions": integrity_data.get("review_exceptions", []),
                "field_confidence": integrity_data.get("field_confidence", {}),
                "document_confidence": integrity_data.get("document_confidence", 1.0),
                "needs_review": integrity_data.get("needs_review", False),
                "review_fields": integrity_data.get("review_fields", []),
                "pipeline_stage": "extracted",
                "latency": {"extraction_seconds": extraction_latency},
            },
            request_id=session["session_id"],
        )

    except ExtractionFailedError as e:
        return JSONResponse(
            _taxio_response(error={"code": e.code, "message": e.message}, ok=False),
            status_code=500,
        )
    except Exception as e:
        return JSONResponse(
            _taxio_response(error={"code": "EXTRACT_FAILED", "message": str(e)}, ok=False),
            status_code=500,
        )


@app.post("/api/correct")
async def api_correct(
    body: CorrectBody,
    taxio_session: str | None = Cookie(None),
    x_session_id: str | None = Header(None),
):
    """Apply corrections to extracted fields and re-validate."""
    try:
        sid = _resolve_session_id(taxio_session, x_session_id)
        session = _get_session(sid)
        if not session:
            return JSONResponse(
                _taxio_response(
                    error={"code": "NO_SESSION", "message": "No active session."},
                    ok=False,
                ),
                status_code=401,
            )

        if session["pipeline_stage"] not in ("extracted", "corrected"):
            return JSONResponse(
                _taxio_response(
                    error={"code": "INVALID_STAGE", "message": f"Cannot correct at stage '{session['pipeline_stage']}'."},
                    ok=False,
                ),
                status_code=400,
            )

        form_type = session["form_type"]
        extracted_fields = session["extracted_fields"]
        doc_id = session.get("document_id")

        escalated = _get_escalated_exceptions(doc_id) if doc_id else []
        context = {"workflow": {"escalated_exceptions": escalated}}

        result = await asyncio.to_thread(
            _data_integrity.apply_fixes,
            form_type,
            extracted_fields,
            body.corrections,
            context,
            session.get("pdf_type"),
            body.human_verified_fields
        )
        integrity_data = result["data"]

        patched = integrity_data.get("patched_fields") or extracted_fields
        session["extracted_fields"] = patched
        session["current_exceptions"] = integrity_data.get("exceptions", [])
        session["correction_history"].append({
            "corrections": body.corrections,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        session["pipeline_stage"] = "corrected"
        session["ui_status"] = STATUS_MAP.get("FIXES_APPLIED", "processing")

        await log_event("CORRECT", f"fixes={len(body.corrections)}", session["session_id"])

        # Update ledger status to VALIDATED
        await asyncio.to_thread(
            _submit_to_ledger,
            filename=session.get("filename", "unknown"),
            form_type=form_type,
            confidence_score=integrity_data.get("document_confidence", 1.0),
            context={"tax_year": datetime.now().year},
            extraction_data=patched,
            validation_data=integrity_data,
            stage="Correction",
            status="VALIDATED"
        )

        return _taxio_response(
            data={
                "form_type": form_type,
                "document_id": session.get("document_id"),
                "extracted_fields": patched,
                "exceptions": integrity_data.get("exceptions", []),
                "fixable_exceptions": integrity_data.get("fixable_exceptions", []),
                "review_exceptions": integrity_data.get("review_exceptions", []),
                "field_confidence": integrity_data.get("field_confidence", {}),
                "document_confidence": integrity_data.get("document_confidence", 1.0),
                "needs_review": integrity_data.get("needs_review", False),
                "fixes_applied": integrity_data.get("fixes_applied", len(body.corrections)),
                "pipeline_stage": "corrected",
            },
            request_id=session["session_id"],
        )

    except Exception as e:
        return JSONResponse(
            _taxio_response(error={"code": "CORRECT_FAILED", "message": str(e)}, ok=False),
            status_code=500,
        )


@app.post("/api/export")
async def api_export(
    body: ExportQuery,
    taxio_session: str | None = Cookie(None),
    x_session_id: str | None = Header(None),
):
    """Export extracted data as a downloadable file (JSON or CSV)."""
    try:
        sid = _resolve_session_id(taxio_session, x_session_id)
        session = _get_session(sid)
        if not session:
            return JSONResponse(
                _taxio_response(
                    error={"code": "NO_SESSION", "message": "No active session."},
                    ok=False,
                ),
                status_code=401,
            )

        if session.get("extracted_fields") is None:
            return JSONResponse(
                _taxio_response(
                    error={"code": "NO_DATA", "message": "No extracted data. Run extraction first."},
                    ok=False,
                ),
                status_code=400,
            )

        form_type = session["form_type"]
        extracted_fields = session["extracted_fields"]
        exceptions = session.get("current_exceptions", [])

        pipeline = {
            "val_result": {
                "exceptions": exceptions,
                "errors":     [],
                "confidence": 1.0,
                "summary":    {},
            },
            "fixable_exceptions": [],
            "review_exceptions":  [],
            "confidence_result": {
                "field_scores":        {},
                "document_confidence": 1.0,
                "needs_review":        False,
                "review_fields":       [],
            },
        }

        export_result = _export_formatter.format_extraction(
            form_type=form_type,
            validated_data=extracted_fields,
            pipeline_result=pipeline,
            pdf_type=session.get("pdf_type") or "digital",
        )

        session["pipeline_stage"] = "exported"
        session["ui_status"] = STATUS_MAP.get("EXPORT_READY", "approved")
        await log_event("EXPORT", f"form={form_type} format={body.format}", session["session_id"])

        safe_name = form_type.replace(" ", "_").replace("/", "-")
        export_fmt = body.format.lower()

        if export_fmt == "csv":
            import io
            import csv as csv_mod
            csv_data = export_result.get("csv_row", {})
            output = io.StringIO()
            if csv_data:
                writer = csv_mod.DictWriter(output, fieldnames=csv_data.keys())
                writer.writeheader()
                writer.writerow(csv_data)
            content = output.getvalue()
            return StreamingResponse(
                iter([content]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={safe_name}_export.csv"},
            )

        json_data = export_result.get("formatted_json", extracted_fields)
        content = json.dumps(json_data, indent=2, default=str)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={safe_name}_export.json"},
        )

    except Exception as e:
        return JSONResponse(
            _taxio_response(error={"code": "EXPORT_FAILED", "message": str(e)}, ok=False),
            status_code=500,
        )


@app.get("/api/session")
def api_session_get(
    taxio_session: str | None = Cookie(None),
    x_session_id: str | None = Header(None),
):
    sid = _resolve_session_id(taxio_session, x_session_id)
    session = _get_session(sid)
    if not session:
        return JSONResponse(
            _taxio_response(
                error={"code": "NO_SESSION", "message": "No active session."},
                ok=False,
            ),
            status_code=401,
        )
    safe_session = {k: v for k, v in session.items() if k not in ("raw_text", "_document_bytes_b64")}
    return _taxio_response(data=safe_session, request_id=session["session_id"])


@app.delete("/api/session")
def api_session_delete(
    response: Response,
    taxio_session: str | None = Cookie(None),
    x_session_id: str | None = Header(None),
):
    sid = _resolve_session_id(taxio_session, x_session_id)
    if sid and sid in SESSIONS:
        del SESSIONS[sid]
    response.delete_cookie(COOKIE_NAME)
    return _taxio_response(data={"cleared": True})


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE GROUP B — Observability & Session Stage routes
# ═══════════════════════════════════════════════════════════════════════════════

class StageUpdateBody(BaseModel):
    model_config = {"extra": "allow"}
    pipeline_stage: str | None = None
    ui_status: str | None = None
    client_name: str | None = None


@app.get("/api/stats")
def api_stats():
    now = datetime.now(timezone.utc)
    active = sum(1 for s in SESSIONS.values() if datetime.fromisoformat(s["expires_at"]) > now)
    stages: dict[str, int] = {}
    for s in SESSIONS.values():
        stage = s.get("pipeline_stage", "unknown")
        stages[stage] = stages.get(stage, 0) + 1
    return _taxio_response(data={
        "active_sessions": active,
        "total_sessions": len(SESSIONS),
        "events_logged": len(_event_log),
        "agent_actions_logged": len(_agent_log),
        "pipeline_stages": stages,
    })


@app.get("/api/events")
async def api_events(session_id: str | None = None, limit: int = 100):
    async with _log_lock:
        entries = list(_event_log)
    if session_id:
        entries = [e for e in entries if e.get("session_id") == session_id]
    return _taxio_response(data={"events": entries[-limit:]})


@app.get("/api/logs")
async def api_logs(session_id: str | None = None, limit: int = 100):
    async with _log_lock:
        entries = list(_agent_log)
    if session_id:
        entries = [e for e in entries if e.get("session_id") == session_id]
    return _taxio_response(data={"logs": entries[-limit:]})


@app.patch("/api/session/stage")
async def api_session_stage(
    body: StageUpdateBody,
    taxio_session: str | None = Cookie(None),
    x_session_id: str | None = Header(None),
):
    sid = _resolve_session_id(taxio_session, x_session_id)
    session = _get_session(sid)
    if not session:
        return JSONResponse(
            _taxio_response(
                error={"code": "NO_SESSION", "message": "No active session."},
                ok=False,
            ),
            status_code=401,
        )
    if body.pipeline_stage is not None:
        session["pipeline_stage"] = body.pipeline_stage
    if body.ui_status is not None:
        session["ui_status"] = body.ui_status
    if body.client_name is not None:
        session["client_name"] = body.client_name

    await log_event("STAGE_UPDATE", f"stage={session['pipeline_stage']} status={session.get('ui_status')}", sid)

    safe_session = {k: v for k, v in session.items() if k not in ("raw_text", "_document_bytes_b64")}
    return _taxio_response(data=safe_session, request_id=session["session_id"])


# ── Static files served by Nginx in production ───────────────────────────────
# app.mount("/static", ...) removed — static assets are in frontend/public/static
# and served directly by Nginx


# ── Startup ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("Taxscio API Gateway starting on http://localhost:8000")
    print("Backend: nuextract.ai hosted API (NuExtract 2.0 PRO)")
    uvicorn.run(app, host="0.0.0.0", port=8000)