#!/usr/bin/env python3
"""Check for duplicate enum values in the database."""
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = "postgresql://postgres:0406@localhost:5432/client_database"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("Checking all lifecycle_stage enums in database...")
    print("=" * 80)
    
    cursor.execute("""
        SELECT 
            enum_type, 
            code, 
            label, 
            sort_order,
            is_active,
            COUNT(*) as duplicate_count
        FROM enum_master 
        WHERE enum_type = 'lifecycle_stage'
        GROUP BY enum_type, code, label, sort_order, is_active
        ORDER BY code, label
    """)
    
    print(f"\n{'CODE':<20} {'LABEL':<20} {'SORT':<5} {'ACTIVE':<8} {'DUPLICATES':<12}")
    print("-" * 80)
    
    all_records = cursor.fetchall()
    total_duplicates = 0
    
    for row in all_records:
        code = row['code'] or 'NULL'
        label = row['label'] or 'NULL'
        sort = row['sort_order'] or 'NULL'
        active = 'Yes' if row['is_active'] else 'No'
        dup_count = row['duplicate_count']
        
        print(f"{code:<20} {label:<20} {str(sort):<5} {active:<8} {str(dup_count):<12}")
        
        if dup_count > 1:
            total_duplicates += dup_count
    
    print("=" * 80)
    
    if total_duplicates > 0:
        print(f"\n⚠️  Found {total_duplicates} duplicate enum entries!")
        print("\nShowing ALL duplicate records:")
        print("-" * 80)
        
        cursor.execute("""
            SELECT 
                id,
                enum_type, 
                code, 
                label, 
                sort_order,
                is_active
            FROM enum_master 
            WHERE enum_type = 'lifecycle_stage'
            ORDER BY code, label, id
        """)
        
        for row in cursor.fetchall():
            print(f"ID: {row['id']:<5} | {row['code']:<15} | {row['label']:<20} | Active: {row['is_active']}")
    else:
        print("\n✓ No duplicates found!")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
