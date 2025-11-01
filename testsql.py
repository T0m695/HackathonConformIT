#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simple SQL Tester - Execute SQL queries directly from Python code
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from typing import List, Dict, Any

load_dotenv()

# --------------------------------------------------------------
# Simple SQL Executor
# --------------------------------------------------------------
def test_sql(query: str, pretty_print: bool = True) -> List[Dict[str, Any]]:
    """
    Execute a SQL query and return results
    
    Args:
        query: SQL query string
        pretty_print: If True, print results nicely
    
    Returns:
        List of dictionaries with results
    """
    conn = None
    try:
        # Connect
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            database=os.getenv("DB_NAME", "events_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "yourpass"),
            cursor_factory=RealDictCursor
        )
        
        cursor = conn.cursor()
        
        # Execute
        cursor.execute(query)
        
        # Get results
        if query.strip().upper().startswith("SELECT"):
            results = cursor.fetchall()
            results = [dict(row) for row in results]
        else:
            conn.commit()
            results = [{"affected_rows": cursor.rowcount}]
        
        cursor.close()
        
        # Pretty print if requested
        if pretty_print:
            print(f"\n{'='*60}")
            print(f"Query: {query[:100]}...")
            print(f"{'='*60}")
            
            if results:
                # Print first 10 rows
                for i, row in enumerate(results[:10], 1):
                    print(f"\nRow {i}:")
                    for key, value in row.items():
                        print(f"  {key}: {value}")
                
                if len(results) > 10:
                    print(f"\n... ({len(results) - 10} more rows)")
                
                print(f"\nTotal: {len(results)} rows")
            else:
                print("No results")
            print(f"{'='*60}\n")
        
        return results
    
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        if conn:
            conn.rollback()
        return []
    
    finally:
        if conn:
            conn.close()


# --------------------------------------------------------------
# Usage Examples
# --------------------------------------------------------------
if __name__ == "__main__":
    

    
    # Example 3: JOIN query
    query = """
SELECT e.event_id, e.type, e.classification, e.start_datetime, e.description 
FROM event e
JOIN event_corrective_measure ecm ON e.event_id = ecm.event_id
JOIN corrective_measure cm ON ecm.measure_id = cm.measure_id
WHERE e.event_id = 1063
LIMIT 100
    """
    results = test_sql(query)    
    
    print(results)