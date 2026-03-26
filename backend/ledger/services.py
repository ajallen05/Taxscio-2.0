import os
from datetime import datetime
import time
from sqlalchemy import func

from .models import DocumentLog, Ledger
from .utils import generate_document_id
from .version_utils import compute_content_hash, has_content_changed


def _require_client_id_on_upload() -> bool:
    return os.environ.get("REQUIRE_CLIENT_ID_ON_UPLOAD", "false").strip().lower() in {"1", "true", "yes", "on"}

def _get_client_id(client_db, client_name):
    """
    Look up client ID from client_database using client_name.
    Returns the UUID string if found, else None.
    """
    if not client_name or not client_db:
        return None
    try:
        # Try to find client by searching through first_name, last_name, business_name, or trust_name
        from backend.client_database.models import Client
        
        normalized_name = client_name.lower().strip()
        
        # Query: find a client where any of the name fields match (case-insensitive)
        client = client_db.query(Client).filter(
            func.lower(
                func.concat(
                    func.coalesce(Client.first_name, ''), ' ',
                    func.coalesce(Client.last_name, '')
                )
            ).like(f'%{normalized_name}%')
        ).first()
        
        # If not found by full name, try business_name or trust_name
        if not client:
            client = client_db.query(Client).filter(
                func.lower(func.coalesce(Client.business_name, '')).like(f'%{normalized_name}%')
            ).first()
        
        if not client:
            client = client_db.query(Client).filter(
                func.lower(func.coalesce(Client.trust_name, '')).like(f'%{normalized_name}%')
            ).first()
        
        return client.id if client else None
    except Exception as e:
        # If client_database query fails, return None gracefully
        print(f"Warning: Failed to fetch client_id for '{client_name}': {e}")
        return None

def create_document(db, data, client_db=None):
    final_status = data.status or "RECEIVED"
    now = datetime.utcnow()
    raw_client_name = (data.client_name or "").strip()
    normalized_client_name = raw_client_name.lower()

    # Reuse existing casing for the same logical client to avoid duplicates like
    # "AARAV SHARMA" vs "Aarav Sharma".
    canonical_client_row = None
    if normalized_client_name:
        canonical_client_row = db.query(Ledger).filter(
            func.lower(func.trim(Ledger.client_name)) == normalized_client_name
        ).order_by(Ledger.id.asc()).first()
    canonical_client_name = canonical_client_row.client_name if canonical_client_row else raw_client_name
    
    # Fetch client_id from client_database
    client_id = None
    if canonical_client_name and client_db:
        client_id = _get_client_id(client_db, canonical_client_name)
    if canonical_client_name and _require_client_id_on_upload() and not client_id:
        raise ValueError(
            f"Client '{canonical_client_name}' was not found in client_database. "
            "Create the client first, then upload the document."
        )
    
    # Keep hashing stable without persisting large payload JSON blobs.
    content_to_hash = {
        "client_name": canonical_client_name,
        "document_type": data.document_type,
        "source": data.source,
        "tax_year": data.tax_year,
        "stage": data.stage,
        "status": final_status,
    }
    content_hash = compute_content_hash(content_to_hash)
    
    # Check if a document for this client and form type already exists
    existing_ledger = db.query(Ledger).filter(
        func.lower(func.trim(Ledger.client_name)) == normalized_client_name,
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
            existing_ledger.client_name = canonical_client_name or data.client_name

        existing_ledger.provider = data.provider
        existing_ledger.description = data.description
        existing_ledger.tax_year = data.tax_year
        if data.cpa is not None:
            existing_ledger.cpa = data.cpa
        if data.due_date is not None:
            existing_ledger.due_date = data.due_date
        if data.confidence_score is not None:
            existing_ledger.confidence_score = data.confidence_score
        if data.local_json_path:
            existing_ledger.local_json_path = data.local_json_path
        # Update client_id if available
        if client_id:
            existing_ledger.client_id = client_id
        existing_ledger.audit_trail = audit_trail
        
        # Create a new version log only if content changed
        if content_changed:
            log = DocumentLog(
                document_id=document_id,
                version=new_version,
                upload_count=new_upload_count,
                content_hash=content_hash,
                client_id=client_id,
                client_name=canonical_client_name,
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
                local_json_path=data.local_json_path or existing_ledger.local_json_path,
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
        client_id=client_id,
        client_name=canonical_client_name,
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
        local_json_path=data.local_json_path,
    )
    db.add(log)

    ledger = Ledger(
        document_id=document_id,
        client_id=client_id,
        client_name=canonical_client_name,
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
        local_json_path=data.local_json_path,
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
        client_id=ledger.client_id,
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
    Persist escalation directly in ledger.audit_trail (single-table flow).
    """
    ledger = None
    if document_id:
        ledger = db.query(Ledger).filter(Ledger.document_id == document_id).first()
    if not ledger and client_name and document_type:
        ledger = db.query(Ledger).filter(
            Ledger.client_name == client_name,
            Ledger.document_type == document_type,
        ).first()

    if not ledger:
        db.commit()
        return {"escalation_id": None, "ledger_linked": False}

    escalation_id = int(time.time() * 1000)
    audit = list(ledger.audit_trail or [])
    audit.append(
        {
            "type": "exception_escalated",
            "time": datetime.utcnow().isoformat() + "Z",
            "exception_code": exception_code,
            "exception_field": exception_field,
            "severity": severity,
            "filename": filename,
            "description": description,
            "payload": extra if isinstance(extra, dict) else {},
            "escalation_id": escalation_id,
        }
    )
    ledger.audit_trail = audit

    db.commit()
    return {"escalation_id": escalation_id, "ledger_linked": True}


def sync_client_ids(db, client_db):
    """
    Backfill ledger/document_logs client_id from client_database using client_name.
    Returns sync counters for observability.
    """
    if not client_db:
        raise RuntimeError("client_database session unavailable")

    total = 0
    matched = 0
    updated_ledger = 0
    updated_logs = 0

    rows = db.query(Ledger).all()
    for row in rows:
        total += 1
        if not row.client_name:
            continue

        client_id = _get_client_id(client_db, row.client_name)
        if not client_id:
            continue
        matched += 1

        if row.client_id != client_id:
            row.client_id = client_id
            updated_ledger += 1

        # Keep historical logs aligned for this document/client.
        logs = db.query(DocumentLog).filter(
            DocumentLog.document_id == row.document_id
        ).all()
        for log_row in logs:
            if log_row.client_id != client_id:
                log_row.client_id = client_id
                updated_logs += 1

    db.commit()
    return {
        "total_ledger_rows": total,
        "matched_clients": matched,
        "updated_ledger_rows": updated_ledger,
        "updated_document_log_rows": updated_logs,
    }


def update_local_json_path(db, document_id: str, local_json_path: str):
    """Persist local JSON path for a ledger document and its logs."""
    if not document_id or not local_json_path:
        return False
    ledger_row = db.query(Ledger).filter(Ledger.document_id == document_id).first()
    if not ledger_row:
        return False
    ledger_row.local_json_path = local_json_path
    logs = db.query(DocumentLog).filter(DocumentLog.document_id == document_id).all()
    for row in logs:
        row.local_json_path = local_json_path
    db.commit()
    return True
