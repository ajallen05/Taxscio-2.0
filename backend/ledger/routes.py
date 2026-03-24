from flask import Blueprint, request, jsonify
from pydantic import ValidationError
from .database import SessionLocal
from .models import Ledger
from .schemas import DocumentCreate
from .services import create_document, record_exception_escalation, update_status

ledger_bp = Blueprint("ledger", __name__)

@ledger_bp.route("/submit", methods=["POST"])
def submit_document():
    if not SessionLocal:
        return jsonify({"error": "Database not configured"}), 500
    
    try:
        data = DocumentCreate(**request.json)
    except ValidationError as e:
        return jsonify({"error": "Validation Error", "details": e.errors()}), 400
        
    db = SessionLocal()
    try:
        doc_id = create_document(db, data)
        return jsonify({"document_id": doc_id})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@ledger_bp.route("/extracted/<document_id>", methods=["PATCH"])
def extracted_doc(document_id):
    if not SessionLocal:
        return jsonify({"error": "Database not configured"}), 500
    db = SessionLocal()
    try:
        updated = update_status(db, document_id, "EXTRACTED")
        if not updated:
            return jsonify({"error": "not found"}), 404
        return jsonify({"message": "updated"})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@ledger_bp.route("/validated/<document_id>", methods=["PATCH"])
def validated_doc(document_id):
    if not SessionLocal:
        return jsonify({"error": "Database not configured"}), 500
    db = SessionLocal()
    try:
        updated = update_status(db, document_id, "VALIDATED")
        if not updated:
            return jsonify({"error": "not found"}), 404
        return jsonify({"message": "updated"})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@ledger_bp.route("/escalate-exception", methods=["POST"])
def escalate_exception():
    """Persist CPA escalation from Exceptions UI; optional link to ledger row by document_id or client+form."""
    if not SessionLocal:
        return jsonify({"error": "Database not configured"}), 503
    body = request.get_json(force=True, silent=True) or {}
    document_id = body.get("document_id") or body.get("documentId")
    client_name = body.get("client_name")
    document_type = body.get("document_type") or body.get("form_type")

    db = SessionLocal()
    try:
        result = record_exception_escalation(
            db,
            document_id=document_id,
            client_name=client_name,
            document_type=document_type,
            exception_code=body.get("exception_code"),
            exception_field=body.get("exception_field"),
            severity=body.get("severity"),
            description=body.get("description"),
            filename=body.get("filename"),
            extra=body.get("payload") if isinstance(body.get("payload"), dict) else {},
        )
        return jsonify({"ok": True, **result})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e), "ok": False}), 500
    finally:
        db.close()


@ledger_bp.route("/ledger", methods=["GET"])
def get_ledger():
    if not SessionLocal:
        return jsonify({"error": "Database not configured"}), 500
    db = SessionLocal()
    try:
        ledgers = db.query(Ledger).all()
        result = []
        for l in ledgers:
            result.append({
                "document_id": l.document_id,
                "client_name": l.client_name,
                "document_type": l.document_type,
                "provider": l.provider,
                "description": l.description,
                "source": l.source,
                "tax_year": l.tax_year,
                "stage": l.stage,
                "status": l.status,
                "version": l.version,
                "upload_count": l.upload_count,
                "cpa": l.cpa,
                "due_date": l.due_date,
                "confidence_score": l.confidence_score,
                "audit_trail": l.audit_trail or [],
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
