#!/usr/bin/env python3
"""
Import sample filing pipeline data for teammates.

Usage:
  python backend/sample_data/import_sample_data.py
  python backend/sample_data/import_sample_data.py --per-client 3 --limit 20
  python backend/sample_data/import_sample_data.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import psycopg2
from psycopg2.extras import Json, RealDictCursor

DEFAULT_CLIENT_DB_URL = "postgresql://postgres:sujan%402004@localhost:5432/client_database"
DEFAULT_LEDGER_DB_URL = "postgresql://postgres:sujan%402004@localhost:5432/ledger_db"
CLIENT_DB_URL = os.getenv("CLIENT_DATABASE_URL", DEFAULT_CLIENT_DB_URL)
LEDGER_DB_URL = os.getenv("DATABASE_URL", DEFAULT_LEDGER_DB_URL)

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
STAGES = [
    "Document Collection",
    "AI Processing",
    "Exception Review",
    "CPA Review",
    "Client Approval",
    "Ready to E-File",
    "Filed & Confirmed",
]
CPA_POOL = ["Jane Smith", "John Doe", "Alice Johnson", None]


@dataclass
class ClientRow:
    id: str
    client_name: str
    lifecycle_stage: str | None


def _safe_client_name(row: dict) -> str:
    name = (row.get("business_name") or "").strip()
    if name:
        return name
    name = (row.get("trust_name") or "").strip()
    if name:
        return name
    first = (row.get("first_name") or "").strip()
    last = (row.get("last_name") or "").strip()
    full = f"{first} {last}".strip()
    return full or "Unknown Client"


def _load_document_types() -> list[str]:
    doc_types = sorted([p.stem for p in SCHEMA_DIR.glob("*.json")])
    if not doc_types:
        raise RuntimeError(f"No form schemas found in {SCHEMA_DIR}")
    return doc_types


def _fetch_clients(limit: int | None) -> list[ClientRow]:
    query = """
        SELECT
            id,
            first_name,
            last_name,
            business_name,
            trust_name,
            lifecycle_stage
        FROM clients
        ORDER BY created_at DESC
    """
    if limit and limit > 0:
        query += " LIMIT %s"

    with psycopg2.connect(CLIENT_DB_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if limit and limit > 0:
                cur.execute(query, (limit,))
            else:
                cur.execute(query)
            rows = cur.fetchall()

    clients: list[ClientRow] = []
    for row in rows:
        clients.append(
            ClientRow(
                id=str(row["id"]),
                client_name=_safe_client_name(row),
                lifecycle_stage=row.get("lifecycle_stage"),
            )
        )
    return clients


def _pick_status(stage: str) -> str:
    if stage in {"Ready to E-File", "Filed & Confirmed"}:
        return "Complete"
    if stage in {"Exception Review", "CPA Review"}:
        return random.choice(["In Progress", "Pending", "Exception"])
    return random.choice(["Complete", "In Progress", "Pending"])


def _build_rows(clients: Iterable[ClientRow], doc_types: list[str], per_client: int, tax_year: int) -> list[tuple]:
    rows: list[tuple] = []
    for client in clients:
        count = min(per_client, len(doc_types))
        chosen = random.sample(doc_types, count)

        for form in chosen:
            document_id = f"doc-{uuid.uuid4().hex[:12]}"
            stage = random.choice(STAGES)
            status = _pick_status(stage)
            confidence_score = round(random.uniform(0.72, 0.99), 2)
            upload_count = random.randint(1, 2)
            version = upload_count
            due_date = (date.today() + timedelta(days=random.randint(7, 60))).isoformat()
            audit_trail = [
                {
                    "stage": stage,
                    "status": status,
                    "time": datetime.utcnow().isoformat(),
                    "upload_count": upload_count,
                    "version": version,
                    "content_changed": True,
                }
            ]
            content_hash = uuid.uuid4().hex + uuid.uuid4().hex

            row = (
                document_id,
                client.id,
                client.client_name,
                form,
                "Taxscio AI",
                f"Sample import: {form} for {client.client_name}",
                "sample_import",
                tax_year,
                stage,
                status,
                version,
                upload_count,
                content_hash,
                audit_trail,
                random.choice(CPA_POOL),
                due_date,
                confidence_score,
            )
            rows.append(row)
    return rows


def _insert_rows(rows: list[tuple], dry_run: bool) -> int:
    ledger_sql = """
        INSERT INTO ledger (
            document_id, client_id, client_name, document_type, provider, description,
            source, tax_year, stage, status, version, upload_count,
            content_hash, audit_trail, cpa, due_date, confidence_score
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    log_sql = """
        INSERT INTO document_logs (
            document_id, version, upload_count, content_hash, client_id, client_name,
            document_type, provider, description, source, tax_year, stage, status,
            cpa, due_date, confidence_score
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    if dry_run:
        return len(rows)

    with psycopg2.connect(LEDGER_DB_URL) as conn:
        with conn.cursor() as cur:
            for row in rows:
                ledger_row = list(row)
                ledger_row[13] = Json(ledger_row[13])
                cur.execute(ledger_sql, tuple(ledger_row))
                cur.execute(
                    log_sql,
                    (
                        row[0],   # document_id
                        row[10],  # version
                        row[11],  # upload_count
                        row[12],  # content_hash
                        row[1],   # client_id
                        row[2],   # client_name
                        row[3],   # document_type
                        row[4],   # provider
                        row[5],   # description
                        row[6],   # source
                        row[7],   # tax_year
                        row[8],   # stage
                        row[9],   # status
                        row[14],  # cpa
                        row[15],  # due_date
                        row[16],  # confidence_score
                    ),
                )
        conn.commit()
    return len(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import sample data into ledger/document_logs")
    parser.add_argument("--per-client", type=int, default=3, help="Number of sample documents per client")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of clients (0 means all)")
    parser.add_argument("--tax-year", type=int, default=2025, help="Tax year to stamp on inserted rows")
    parser.add_argument("--dry-run", action="store_true", help="Preview row count without inserting")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.per_client <= 0:
        raise SystemExit("--per-client must be greater than 0")

    document_types = _load_document_types()
    clients = _fetch_clients(args.limit if args.limit > 0 else None)
    if not clients:
        raise SystemExit("No clients found in client_database.clients")

    rows = _build_rows(clients, document_types, args.per_client, args.tax_year)
    inserted = _insert_rows(rows, args.dry_run)

    mode = "DRY RUN" if args.dry_run else "INSERTED"
    print("=" * 72)
    print(f"{mode}: {inserted} sample rows")
    print(f"Clients considered: {len(clients)} | Docs per client: {args.per_client}")
    print(f"Target DB: {LEDGER_DB_URL}")
    print("=" * 72)


if __name__ == "__main__":
    main()
