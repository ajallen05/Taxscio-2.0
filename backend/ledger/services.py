from datetime import datetime
from .models import DocumentLog, Ledger
from .utils import generate_document_id

from datetime import datetime
import time

def create_document(db, data):
    final_status = data.status or "RECEIVED"
    now = datetime.utcnow()
    
    # Check if a document for this client and form type already exists
    existing_ledger = db.query(Ledger).filter(
        Ledger.client_name == data.client_name,
        Ledger.document_type == data.document_type
    ).first()

    if existing_ledger:
        document_id = existing_ledger.document_id
        new_version = existing_ledger.version + 1
        
        # Always intelligently append the current stage and status to the history trail natively
        audit_trail = existing_ledger.audit_trail if existing_ledger.audit_trail else []
        audit_trail = list(audit_trail)
        audit_trail.append({"stage": data.stage, "status": final_status, "time": str(now)})

        existing_ledger.stage = data.stage
        existing_ledger.status = final_status
        
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
        
        # Create a new version log
        log = DocumentLog(
            document_id=document_id,
            version=new_version,
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
    
    audit_trail = [{"stage": data.stage, "status": final_status, "time": str(now)}]

    log = DocumentLog(
        document_id=document_id,
        version=1,
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
        
    latest_version = ledger.version
    log = DocumentLog(
        document_id=document_id,
        version=latest_version,
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
