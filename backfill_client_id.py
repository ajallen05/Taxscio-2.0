#!/usr/bin/env python3
"""
Backfill script to populate client_id in ledger and document_logs tables
by matching client_name with the client_database clients table.
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.ledger.database import SessionLocal as LedgerSessionLocal
from backend.client_database.database import SessionLocal as ClientSessionLocal
from backend.ledger.models import Ledger, DocumentLog
from backend.client_database.models import Client
from sqlalchemy import func


def get_client_id(client_db, client_name):
    """Look up client ID from client_database using client_name."""
    if not client_name or not client_db:
        return None
    try:
        normalized_name = client_name.lower().strip()
        
        # Try to find client by full name (first_name + last_name)
        client = client_db.query(Client).filter(
            func.lower(
                func.concat(
                    func.coalesce(Client.first_name, ''), ' ',
                    func.coalesce(Client.last_name, '')
                )
            ).like(f'%{normalized_name}%')
        ).first()
        
        # If not found, try business_name
        if not client:
            client = client_db.query(Client).filter(
                func.lower(func.coalesce(Client.business_name, '')).like(f'%{normalized_name}%')
            ).first()
        
        # If not found, try trust_name
        if not client:
            client = client_db.query(Client).filter(
                func.lower(func.coalesce(Client.trust_name, '')).like(f'%{normalized_name}%')
            ).first()
        
        return client.id if client else None
    except Exception as e:
        print(f"Error fetching client_id for '{client_name}': {e}")
        return None


def backfill_ledger_client_ids():
    """Backfill client_id for all ledger records."""
    if not LedgerSessionLocal or not ClientSessionLocal:
        print("Error: Database sessions not initialized")
        return
    
    ledger_db = LedgerSessionLocal()
    client_db = ClientSessionLocal()
    
    try:
        # Get all ledger records without client_id
        records = ledger_db.query(Ledger).filter(Ledger.client_id == None).all()
        print(f"Found {len(records)} ledger records without client_id")
        
        updated_count = 0
        for record in records:
            if record.client_name:
                client_id = get_client_id(client_db, record.client_name)
                if client_id:
                    record.client_id = client_id
                    updated_count += 1
                    print(f"✓ Updated ledger {record.document_id}: client_name='{record.client_name}' -> client_id='{client_id}'")
                else:
                    print(f"✗ No client found for '{record.client_name}'")
        
        ledger_db.commit()
        print(f"\nBackfilled {updated_count}/{len(records)} ledger records")
    except Exception as e:
        ledger_db.rollback()
        print(f"Error during ledger backfill: {e}")
    finally:
        ledger_db.close()
        client_db.close()


def backfill_document_log_client_ids():
    """Backfill client_id for all document_logs records."""
    if not LedgerSessionLocal or not ClientSessionLocal:
        print("Error: Database sessions not initialized")
        return
    
    ledger_db = LedgerSessionLocal()
    client_db = ClientSessionLocal()
    
    try:
        # Get all document_logs records without client_id
        records = ledger_db.query(DocumentLog).filter(DocumentLog.client_id == None).all()
        print(f"\nFound {len(records)} document_logs records without client_id")
        
        updated_count = 0
        for record in records:
            if record.client_name:
                client_id = get_client_id(client_db, record.client_name)
                if client_id:
                    record.client_id = client_id
                    updated_count += 1
                    print(f"✓ Updated document_log {record.document_id} v{record.version}: client_name='{record.client_name}' -> client_id='{client_id}'")
                else:
                    print(f"✗ No client found for '{record.client_name}'")
        
        ledger_db.commit()
        print(f"\nBackfilled {updated_count}/{len(records)} document_logs records")
    except Exception as e:
        ledger_db.rollback()
        print(f"Error during document_logs backfill: {e}")
    finally:
        ledger_db.close()
        client_db.close()


if __name__ == "__main__":
    print("=" * 70)
    print("BACKFILL CLIENT_ID SCRIPT")
    print("=" * 70)
    
    backfill_ledger_client_ids()
    backfill_document_log_client_ids()
    
    print("\n" + "=" * 70)
    print("Backfill complete!")
    print("=" * 70)
