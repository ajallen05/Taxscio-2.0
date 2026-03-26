#!/usr/bin/env python3
"""
Generate sample filing pipeline data from existing clients in client_database.
Creates ledger entries with documents for each client.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid
from datetime import datetime, timedelta
import random
import os
from pathlib import Path

DEFAULT_CLIENT_DB_URL = "postgresql://postgres:0406@localhost:5432/client_database"
DEFAULT_LEDGER_DB_URL = "postgresql://postgres:0406@localhost:5432/ledgerdb"
CLIENT_DB_URL = os.getenv("CLIENT_DATABASE_URL", DEFAULT_CLIENT_DB_URL)
LEDGER_DB_URL = os.getenv("DATABASE_URL", DEFAULT_LEDGER_DB_URL)

SCHEMA_DIR = Path(__file__).resolve().parent / "backend" / "schemas"

# Valid form types are loaded from backend/schemas/*.json only.
DOCUMENT_TYPES = sorted([p.stem for p in SCHEMA_DIR.glob("*.json")])
if not DOCUMENT_TYPES:
    raise RuntimeError(f"No form schemas found in {SCHEMA_DIR}")

STAGES = ["Document Collection", "AI Processing", "Exception Review", "CPA Review", "Client Approval", "Ready to E-File", "Filed & Confirmed"]
STATUSES = ["Complete", "In Progress", "Pending", "Exception"]

def get_existing_clients():
    """Fetch all clients from client_database."""
    try:
        conn = psycopg2.connect(CLIENT_DB_URL)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT 
                id,
                COALESCE(
                    NULLIF(TRIM(business_name), ''),
                    NULLIF(TRIM(trust_name), ''),
                    NULLIF(TRIM(CONCAT_WS(' ', first_name, last_name)), ''),
                    'Unknown Client'
                ) as client_name,
                entity_type,
                lifecycle_stage
            FROM clients
            ORDER BY created_at DESC
            LIMIT 100
        """)
        
        clients = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return clients
    except Exception as e:
        print(f"Error fetching clients: {e}")
        return []

def generate_sample_ledger_entries(clients):
    """Generate sample ledger entries for each client."""
    try:
        conn = psycopg2.connect(LEDGER_DB_URL)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("Generating sample filing pipeline data from existing clients")
        print("=" * 80)
        
        total_inserted = 0
        
        for client in clients:
            client_name = client['client_name']
            
            # Generate 2-4 documents per client
            num_docs = random.randint(2, 4)
            selected_docs = random.sample(DOCUMENT_TYPES, min(num_docs, len(DOCUMENT_TYPES)))
            
            print(f"\n📋 {client_name}")
            
            for i, doc_type in enumerate(selected_docs):
                try:
                    document_id = f"doc-{uuid.uuid4().hex[:12]}"
                    
                    # Randomize stage and confidence
                    stage = random.choice(STAGES)
                    confidence = round(random.uniform(0.65, 0.99), 2)
                    status = "Complete" if stage in ["Ready to E-File", "Filed & Confirmed"] else random.choice(["Complete", "In Progress"])
                    
                    # Due date: 1-60 days from now
                    days_offset = random.randint(1, 60)
                    due_date = (datetime.now() + timedelta(days=days_offset)).date()
                    
                    cursor.execute("""
                        INSERT INTO ledger (
                            document_id, client_name, document_type, provider, description,
                            source, tax_year, stage, status, version, upload_count,
                            content_hash, cpa, due_date, confidence_score
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        document_id,
                        client_name,
                        doc_type,
                        "OCR_ENGINE",
                        f"{doc_type} for {client_name}",
                        "file_upload",
                        2025,
                        stage,
                        status,
                        1,
                        1,
                        f"sha256_{uuid.uuid4().hex[:16]}",
                        random.choice(["Jane Smith", "John Doe", "Alice Johnson", None]),
                        due_date.isoformat(),
                        confidence,
                    ))
                    
                    conf_color = "🟢" if confidence >= 0.90 else "🟡" if confidence >= 0.75 else "🔴"
                    print(f"   {conf_color} {doc_type:15} | Stage: {stage:25} | Conf: {confidence*100:.0f}%")
                    total_inserted += 1
                    
                except Exception as e:
                    print(f"   ✗ Error inserting {doc_type}: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 80)
        print(f"✓ Successfully inserted {total_inserted} documents!")
        print("=" * 80)
        print("\nNow refresh your Filing Pipeline view to see the data.")
        
        return total_inserted
        
    except Exception as e:
        print(f"Error inserting ledger entries: {e}")
        import traceback
        traceback.print_exc()
        return 0

def verify_data():
    """Verify the inserted data."""
    try:
        conn = psycopg2.connect(LEDGER_DB_URL)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("\n" + "=" * 80)
        print("Verification - Sample of generated data:")
        print("=" * 80)
        
        cursor.execute("""
            SELECT 
                client_name,
                document_type,
                stage,
                confidence_score,
                status,
                due_date
            FROM ledger
            ORDER BY RANDOM()
            LIMIT 15
        """)
        
        for row in cursor.fetchall():
            conf_pct = f"{row['confidence_score']*100:.0f}%"
            print(f"  {row['client_name']:40} | {row['document_type']:10} | {row['stage']:20} | {conf_pct:>4}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error verifying data: {e}")

if __name__ == "__main__":
    # Step 1: Get existing clients
    print("Fetching existing clients from client_database...\n")
    clients = get_existing_clients()
    
    if not clients:
        print("❌ No clients found in client_database.")
        exit(1)
    
    print(f"✓ Found {len(clients)} clients\n")
    
    # Step 2: Generate sample ledger entries
    inserted = generate_sample_ledger_entries(clients)
    
    # Step 3: Verify
    if inserted > 0:
        verify_data()
