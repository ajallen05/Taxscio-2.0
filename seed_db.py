import psycopg2
import os

# Database connection details
db_url = "postgresql://postgres:sujan%402004@localhost:5432/client_database"
conn = psycopg2.connect(db_url)
conn.autocommit = True
cursor = conn.cursor()

# Read the SQL file
with open('backend/client_database/seed_client_database.sql', 'r') as f:
    sql = f.read()

# Split by semicolon and execute each statement
statements = sql.split(';')
for statement in statements:
    statement = statement.strip()
    if statement:
        try:
            cursor.execute(statement)
            print(f"Executed: {statement[:50]}...")
        except Exception as e:
            print(f"Error executing: {statement[:50]}... {e}")

conn.close()
print("Database seeded.")