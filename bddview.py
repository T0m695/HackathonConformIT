#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Database Schema Visualizer
Generates visual schema diagrams from PostgreSQL database
Outputs: Mermaid diagram, ASCII art, and optionally GraphViz
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from typing import List, Dict, Any
from collections import defaultdict

load_dotenv()

# --------------------------------------------------------------
# Database Schema Extractor
# --------------------------------------------------------------
class SchemaExtractor:
    """Extract database schema information"""
    
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            database=os.getenv("DB_NAME", "events_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "yourpass"),
            cursor_factory=RealDictCursor
        )
        self.cursor = self.conn.cursor()
    
    def get_tables(self) -> List[Dict]:
        """Get all tables in the database"""
        query = """
        SELECT 
            table_name,
            obj_description((quote_ident(table_schema)||'.'||quote_ident(table_name))::regclass, 'pg_class') as description
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
        """
        self.cursor.execute(query)
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_columns(self, table_name: str) -> List[Dict]:
        """Get all columns for a table"""
        query = """
        SELECT 
            c.column_name,
            c.data_type,
            c.character_maximum_length,
            c.is_nullable,
            c.column_default,
            col_description((quote_ident(c.table_schema)||'.'||quote_ident(c.table_name))::regclass, c.ordinal_position) as description,
            CASE 
                WHEN pk.column_name IS NOT NULL THEN true 
                ELSE false 
            END as is_primary_key
        FROM information_schema.columns c
        LEFT JOIN (
            SELECT ku.table_name, ku.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage ku
                ON tc.constraint_name = ku.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
        ) pk ON c.table_name = pk.table_name AND c.column_name = pk.column_name
        WHERE c.table_name = %s
        ORDER BY c.ordinal_position;
        """
        self.cursor.execute(query, (table_name,))
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_foreign_keys(self) -> List[Dict]:
        """Get all foreign key relationships"""
        query = """
        SELECT
            tc.table_name as from_table,
            kcu.column_name as from_column,
            ccu.table_name as to_table,
            ccu.column_name as to_column,
            tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        ORDER BY tc.table_name, kcu.column_name;
        """
        self.cursor.execute(query)
        return [dict(row) for row in self.cursor.fetchall()]
    
    def close(self):
        """Close database connection"""
        self.cursor.close()
        self.conn.close()

# --------------------------------------------------------------
# Mermaid Diagram Generator
# --------------------------------------------------------------
def generate_mermaid_diagram(extractor: SchemaExtractor) -> str:
    """Generate Mermaid ERD diagram"""
    tables = extractor.get_tables()
    foreign_keys = extractor.get_foreign_keys()
    
    mermaid = ["erDiagram"]
    
    # Add tables with columns
    for table in tables:
        table_name = table['table_name']
        columns = extractor.get_columns(table_name)
        
        mermaid.append(f"\n    {table_name.upper()} ")
        
        for col in columns:
            col_type = col['data_type']
            if col['character_maximum_length']:
                col_type += f"({col['character_maximum_length']})"
            
            pk_marker = " PK" if col['is_primary_key'] else ""
            nullable = "" if col['is_nullable'] == 'YES' else " NOT NULL"
            
            mermaid.append(f"        {col_type} {col['column_name']}{pk_marker}{nullable}")
        
        mermaid.append("    }")
    
    # Add relationships
    mermaid.append("")
    for fk in foreign_keys:
        # Mermaid syntax: TableA ||--o{ TableB : relationship
        mermaid.append(f"    {fk['from_table'].upper()} ||--o{{ {fk['to_table'].upper()} : \"{fk['from_column']}\"")
    
    return "\n".join(mermaid)

# --------------------------------------------------------------
# ASCII Art Generator
# --------------------------------------------------------------
def generate_ascii_diagram(extractor: SchemaExtractor) -> str:
    """Generate ASCII art diagram"""
    tables = extractor.get_tables()
    foreign_keys = extractor.get_foreign_keys()
    
    output = []
    output.append("=" * 80)
    output.append("DATABASE SCHEMA".center(80))
    output.append("=" * 80)
    output.append("")
    
    # Tables
    for table in tables:
        table_name = table['table_name']
        columns = extractor.get_columns(table_name)
        
        # Table header
        output.append("┌" + "─" * 78 + "┐")
        output.append(f"│ TABLE: {table_name.upper():<70} │")
        
        if table['description']:
            output.append(f"│ {table['description']:<76} │")
        
        output.append("├" + "─" * 78 + "┤")
        
        # Columns
        for col in columns:
            pk = "🔑" if col['is_primary_key'] else "  "
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            
            col_type = col['data_type']
            if col['character_maximum_length']:
                col_type += f"({col['character_maximum_length']})"
            
            col_line = f"{pk} {col['column_name']:<25} {col_type:<20} {nullable:<10}"
            output.append(f"│ {col_line:<76} │")
        
        output.append("└" + "─" * 78 + "┘")
        output.append("")
    
    # Foreign Keys
    output.append("=" * 80)
    output.append("FOREIGN KEY RELATIONSHIPS".center(80))
    output.append("=" * 80)
    output.append("")
    
    for fk in foreign_keys:
        output.append(f"  {fk['from_table']}.{fk['from_column']} ──→ {fk['to_table']}.{fk['to_column']}")
    
    output.append("")
    output.append("=" * 80)
    
    return "\n".join(output)

# --------------------------------------------------------------
# PlantUML Generator
# --------------------------------------------------------------
def generate_plantuml_diagram(extractor: SchemaExtractor) -> str:
    """Generate PlantUML diagram"""
    tables = extractor.get_tables()
    foreign_keys = extractor.get_foreign_keys()
    
    output = ["@startuml", "!define Table(name,desc) class name as \"desc\" << (T,#FFAAAA) >>", ""]
    
    # Tables
    for table in tables:
        table_name = table['table_name']
        columns = extractor.get_columns(table_name)
        
        output.append(f"class {table_name} ")
        
        for col in columns:
            pk = "PK " if col['is_primary_key'] else "   "
            col_type = col['data_type']
            output.append(f"  {pk}{col['column_name']}: {col_type}")
        
        output.append("}")
        output.append("")
    
    # Relationships
    for fk in foreign_keys:
        output.append(f"{fk['from_table']} |--|| {fk['to_table']}")
    
    output.append("@enduml")
    
    return "\n".join(output)

# --------------------------------------------------------------
# Markdown Table Generator
# --------------------------------------------------------------
def generate_markdown_documentation(extractor: SchemaExtractor) -> str:
    """Generate Markdown documentation"""
    tables = extractor.get_tables()
    foreign_keys = extractor.get_foreign_keys()
    
    output = []
    output.append("# Database Schema Documentation\n")
    output.append(f"**Database:** {os.getenv('DB_NAME', 'events_db')}\n")
    output.append(f"**Generated:** {os.popen('date').read().strip()}\n")
    output.append("---\n")
    
    # Table of contents
    output.append("## Tables\n")
    for table in tables:
        output.append(f"- [{table['table_name']}](#{table['table_name']})")
    output.append("\n---\n")
    
    # Tables detail
    for table in tables:
        table_name = table['table_name']
        columns = extractor.get_columns(table_name)
        
        output.append(f"## {table_name}\n")
        
        if table['description']:
            output.append(f"*{table['description']}*\n")
        
        output.append("| Column | Type | Nullable | Key | Description |")
        output.append("|--------|------|----------|-----|-------------|")
        
        for col in columns:
            pk = "PK" if col['is_primary_key'] else ""
            nullable = "✓" if col['is_nullable'] == 'YES' else "✗"
            col_type = col['data_type']
            if col['character_maximum_length']:
                col_type += f"({col['character_maximum_length']})"
            
            desc = col['description'] or ""
            output.append(f"| {col['column_name']} | {col_type} | {nullable} | {pk} | {desc} |")
        
        output.append("\n")
    
    # Foreign Keys
    output.append("## Foreign Key Relationships\n")
    output.append("| From Table | From Column | To Table | To Column |")
    output.append("|------------|-------------|----------|-----------|")
    
    for fk in foreign_keys:
        output.append(f"| {fk['from_table']} | {fk['from_column']} | {fk['to_table']} | {fk['to_column']} |")
    
    return "\n".join(output)

# --------------------------------------------------------------
# Main
# --------------------------------------------------------------
def main():
    """Generate all schema formats"""
    print("🔍 Extracting database schema...")
    
    extractor = SchemaExtractor()
    
    try:
        # Generate Mermaid
        print("📊 Generating Mermaid diagram...")
        mermaid = generate_mermaid_diagram(extractor)
        with open("schema_mermaid.md", "w", encoding="utf-8") as f:
            f.write("```mermaid\n")
            f.write(mermaid)
            f.write("\n```\n")
        print("✅ Saved: schema_mermaid.md")
        
        # Generate ASCII
        print("🎨 Generating ASCII diagram...")
        ascii_art = generate_ascii_diagram(extractor)
        with open("schema_ascii.txt", "w", encoding="utf-8") as f:
            f.write(ascii_art)
        print("✅ Saved: schema_ascii.txt")
        print("\n" + ascii_art)
        
        # Generate PlantUML
        print("\n📐 Generating PlantUML diagram...")
        plantuml = generate_plantuml_diagram(extractor)
        with open("schema_plantuml.puml", "w", encoding="utf-8") as f:
            f.write(plantuml)
        print("✅ Saved: schema_plantuml.puml")
        
        # Generate Markdown
        print("📝 Generating Markdown documentation...")
        markdown = generate_markdown_documentation(extractor)
        with open("schema_documentation.md", "w", encoding="utf-8") as f:
            f.write(markdown)
        print("✅ Saved: schema_documentation.md")
        
        print("\n🎉 All schema files generated successfully!")
        print("\nGenerated files:")
        print("  - schema_mermaid.md      (for GitHub/GitLab)")
        print("  - schema_ascii.txt       (text view)")
        print("  - schema_plantuml.puml   (for PlantUML)")
        print("  - schema_documentation.md (full docs)")
        
    finally:
        extractor.close()

if __name__ == "__main__":
    main()