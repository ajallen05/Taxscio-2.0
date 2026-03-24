from datetime import datetime
import time

from .models import DocumentLog, ExceptionEscalation, Ledger
from .utils import generate_document_id
from .version_utils import compute_content_hash, has_content_changed

def create_document(db, data):
    final_status = data.status or "RECEIVED"
    now = datetime.utcnow()
    
    # Use extraction_data if content_data not provided, otherwise use content_data
    content_to_hash = data.content_data or data.extraction_data or {}
    content_hash = compute_content_hash(content_to_hash)
    
    # Check if a document for this client and form type already exists
    existing_ledger = db.query(Ledger).filter(
        Ledger.client_name == data.client_name,
        Ledger.document_type == data.document_type
    ).first()

    if existing_ledger:
        document_id = existing_ledger.document_id
        
        # Increment upload count always
        existing_upload_count = existing_ledger.upload_count or 1
        new_upload_count = existing_upload_count + 1
        
        # Only increment version if content has changed
        content_changed = has_content_changed(content_hash, existing_ledger.content_hash)
        if content_changed:
            new_version = (existing_ledger.version or 1) + 1
        else:
            new_version = existing_ledger.version or 1
        
        # Always intelligently append the current stage and status to the history trail natively
        audit_trail = existing_ledger.audit_trail if existing_ledger.audit_trail else []
        audit_trail = list(audit_trail)
        audit_trail.append({
            "stage": data.stage,
            "status": final_status,
            "time": str(now),
            "upload_count": new_upload_count,
            "version": new_version,
            "content_changed": content_changed
        })

        existing_ledger.stage = data.stage
        existing_ledger.status = final_status
        existing_ledger.version = new_version
        existing_ledger.upload_count = new_upload_count
        existing_ledger.content_hash = content_hash
        
        # Update client name if the existing one is just a DOC ID or "Unknown"
        if data.client_name and (existing_ledger.client_name.startswith("DOC-") or existing_ledger.client_name == "Unknown"):
            existing_ledger.client_name = data.client_name

        existing_ledger.provider = data.provider
        existing_ledger.description = data.description
        existing_ledger.tax_year = data.tax_year
        if data.cpa is not None:
            existing_ledger.cpa = data.cpa
        if data.due_date is not None:
            existing_ledger.due_date = data.due_date
        if data.confidence_score is not None:
            existing_ledger.confidence_score = data.confidence_score
        existing_ledger.audit_trail = audit_trail
        
        # Create a new version log only if content changed
        if content_changed:
            log = DocumentLog(
                document_id=document_id,
                version=new_version,
                upload_count=new_upload_count,
                content_hash=content_hash,
                client_name=data.client_name,
                document_type=data.document_type,
                provider=data.provider,
                description=data.description,
                source=data.source,
                tax_year=data.tax_year,
                stage=data.stage,
                status=final_status,
                cpa=existing_ledger.cpa,
                due_date=existing_ledger.due_date,
                confidence_score=existing_ledger.confidence_score,
            )
            db.add(log)
        
        db.commit()
        return document_id

    # Normal creation logic for new records
    document_id = generate_document_id()
    
    audit_trail = [{
        "stage": data.stage,
        "status": final_status,
        "time": str(now),
        "upload_count": 1,
        "version": 1,
        "content_changed": True
    }]

    log = DocumentLog(
        document_id=document_id,
        version=1,
        upload_count=1,
        content_hash=content_hash,
        client_name=data.client_name,
        document_type=data.document_type,
        provider=data.provider,
        description=data.description,
        source=data.source,
        tax_year=data.tax_year,
        stage=data.stage,
        status=final_status,
        cpa=data.cpa,
        due_date=data.due_date,
        confidence_score=data.confidence_score,
    )
    db.add(log)

    ledger = Ledger(
        document_id=document_id,
        client_name=data.client_name,
        document_type=data.document_type,
        provider=data.provider,
        description=data.description,
        source=data.source,
        tax_year=data.tax_year,
        stage=data.stage,
        status=final_status,
        version=1,
        upload_count=1,
        content_hash=content_hash,
        audit_trail=audit_trail,
        cpa=data.cpa,
        due_date=data.due_date,
        confidence_score=data.confidence_score,
    )
    db.add(ledger)
    db.commit()
    return document_id

def update_status(db, document_id, status):
    ledger = db.query(Ledger).filter(Ledger.document_id==document_id).first()
    if not ledger:
        return None
        
    latest_version = ledger.version or 1
    log = DocumentLog(
        document_id=document_id,
        version=latest_version,
        upload_count=ledger.upload_count or 1,
        content_hash=ledger.content_hash,
        client_name=ledger.client_name,
        document_type=ledger.document_type,
        provider=ledger.provider,
        description=ledger.description,
        source=ledger.source,
        tax_year=ledger.tax_year,
        stage=ledger.stage,
        status=status,
        cpa=ledger.cpa,
        due_date=ledger.due_date,
        confidence_score=ledger.confidence_score
    )
    db.add(log)
    
    audit = ledger.audit_trail
    if not audit:
        audit = []
    else:
        audit = list(audit)
    audit.append({
        "stage": ledger.stage,
        "status": status,
        "time": str(datetime.utcnow())
    })
    
    ledger.status = status
    ledger.audit_trail = audit
    db.commit()
    return ledger


def record_exception_escalation(
    db,
    *,
    document_id=None,
    client_name=None,
    document_type=None,
    exception_code=None,
    exception_field=None,
    severity=None,
    description=None,
    filename=None,
    extra=None,
):
    """
    Persist an escalation row and, when a matching ledger entry exists,
    append an exception_escalated event to its audit_trail.
    """
    row = ExceptionEscalation(
        document_id=document_id or None,
        client_name=client_name or None,
        document_type=document_type or None,
        filename=filename or None,
        exception_code=exception_code or None,
        exception_field=exception_field or None,
        severity=severity or None,
        description=description or None,
        payload=extra if isinstance(extra, dict) else {},
    )
    db.add(row)
    db.flush()

    ledger = None
    if document_id:
        ledger = db.query(Ledger).filter(Ledger.document_id == document_id).first()
    if not ledger and client_name and document_type:
        ledger = db.query(Ledger).filter(
            Ledger.client_name == client_name,
            Ledger.document_type == document_type,
        ).first()

    if ledger:
        audit = list(ledger.audit_trail or [])
        audit.append(
            {
                "type": "exception_escalated",
                "time": datetime.utcnow().isoformat() + "Z",
                "exception_code": exception_code,
                "exception_field": exception_field,
                "severity": severity,
                "filename": filename,
                "escalation_id": row.id,
            }
        )
        ledger.audit_trail = audit

    db.commit()
    return {"escalation_id": row.id, "ledger_linked": ledger is not None}
