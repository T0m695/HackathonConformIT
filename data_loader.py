import json
from sqlalchemy import create_engine, MetaData

# Replace with your actual database URI
db_uri = "postgresql+psycopg2://postgres:yourpass@localhost:5432/events_db"  # Update password, db name, etc.

# Create engine and reflect metadata
engine = create_engine(db_uri)
metadata = MetaData()
metadata.reflect(engine)

# Build schema dictionary
schema = {
    "tables": {},
    "relationships": []
}

# Extract tables and columns
for table_name, table in metadata.tables.items():
    schema["tables"][table_name] = {
        "columns": [
            {
                "name": column.name,
                "type": str(column.type),
                "synonyms": []  # Add synonyms manually later, e.g., ["alias1", "alias2"]
            } for column in table.columns
        ],
        "description": ""  # Add manual description here, e.g., "Table for events and incidents"
    }

# Infer relationships from foreign keys
for table in metadata.tables.values():
    for fk in table.foreign_keys:
        schema["relationships"].append({
            "from": fk.parent.table.name,
            "to": fk.column.table.name,
            "on": fk.parent.name,
            "type": "foreign_key"
        })

# Add sample queries section (add your examples manually)
schema["sample_queries"] = [
    # Example structure
    {
        "natural_language": "Example query in natural language",
        "sql": "SELECT * FROM public.event WHERE start_time > '2021-01-01';"
    }
    # Add more here
]

# Save to JSON file
with open("schema.json", "w") as f:
    json.dump(schema, f, indent=4)

print("Schema extracted and saved to schema.json")