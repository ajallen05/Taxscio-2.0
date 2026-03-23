import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5432/postgres")
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cursor = conn.cursor()

for db in ["client_database", "ledgerdb"]:
    try:
        cursor.execute(f'CREATE DATABASE {db}')
        print(f"Created {db}")
    except psycopg2.errors.DuplicateDatabase:
        print(f"{db} already exists")

conn.close()
