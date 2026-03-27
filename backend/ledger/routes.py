from flask import Blueprint, request, jsonify
from pydantic import ValidationError
from .database import SessionLocal
from .models import Ledger
from .schemas import DocumentCreate
from .services import create_document, record_exception_escalation, update_status

# local extraction store — update JSON file when exceptions are escalated/resolved
try:
    from backend.local_extraction_store import (
        update_exceptions     as _les_update,
        mark_exception_resolved as _les_resolve,
    )
    _HAS_LES = True
except ImportError:
    _HAS_LES = False

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

@ledger_bp.route("/associate-client", methods=["PATCH"])
def associate_client():
    """
    Backfill client_id on ledger rows that were created before a client was matched.
    Matches rows by client_name + document_type (+ optional tax_year).
    Safe to call multiple times (idempotent).
    """
    if not SessionLocal:
        return jsonify({"error": "Database not configured"}), 503
    body = request.get_json(force=True, silent=True) or {}
    client_id    = body.get("client_id")
    client_name  = body.get("client_name")
    document_type = body.get("document_type")
    tax_year     = body.get("tax_year")

    if not client_id or not client_name:
        return jsonify({"error": "client_id and client_name are required"}), 400

    db = SessionLocal()
    try:
        q = db.query(Ledger).filter(Ledger.client_name == client_name)
        if document_type:
            q = q.filter(Ledger.document_type == document_type)
        if tax_year:
            q = q.filter(Ledger.tax_year == int(tax_year))
        rows = q.all()
        updated = 0
        for row in rows:
            if not row.client_id:
                row.client_id = client_id
                updated += 1
        db.commit()
        return jsonify({"ok": True, "updated_rows": updated})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e), "ok": False}), 500
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
        # Sync the local extraction file:
        # • remove the resolved exception from exceptions[]
        # • append audit event to exception_audit[]
        if _HAS_LES:
            try:
                # Resolve the document_id: use what was sent, else look it up from ledger
                sync_doc_id = document_id
                if not sync_doc_id and (client_name or document_type):
                    row = db.query(Ledger).filter(
                        *(
                            [Ledger.client_name == client_name] if client_name else []
                        ) + (
                            [Ledger.document_type == document_type] if document_type else []
                        )
                    ).order_by(Ledger.id.desc()).first()
                    if row:
                        sync_doc_id = row.document_id

                if sync_doc_id:
                    audit_entry = {
                        "type":            "exception_escalated",
                        "escalation_id":   result.get("escalation_id"),
                        "exception_code":  body.get("exception_code"),
                        "exception_field": body.get("exception_field"),
                        "severity":        body.get("severity"),
                        "description":     body.get("description"),
                        "filename":        body.get("filename"),
                        "time":            __import__("datetime").datetime.utcnow().isoformat() + "Z",
                    }
                    _les_resolve(
                        document_id     = sync_doc_id,
                        exception_code  = body.get("exception_code"),
                        exception_field = body.get("exception_field"),
                        audit_entry     = audit_entry,
                    )
            except Exception:
                pass

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

@ledger_bp.route("/export", methods=["GET"])
def export_ledger():
    if not SessionLocal:
        from flask import jsonify
        return jsonify({"error": "Database not configured"}), 500
    format_type = request.args.get("format", "json")
    db = SessionLocal()
    try:
        ledgers = db.query(Ledger).all()
        result = []
        for l in ledgers:
            result.append({
                "document_id": l.document_id,
                "client_name": l.client_name,
                "document_type": l.document_type,
                "stage": l.stage,
                "status": l.status,
                "confidence_score": l.confidence_score,
                "provider": l.provider,
            })
        if format_type == "csv":
            import io, csv
            from flask import Response
            si = io.StringIO()
            if result:
                writer = csv.DictWriter(si, fieldnames=result[0].keys())
                writer.writeheader()
                writer.writerows(result)
            return Response(si.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=ledger_export.csv"})
        from flask import jsonify
        return jsonify(result)
    except Exception as e:
        from flask import jsonify
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
