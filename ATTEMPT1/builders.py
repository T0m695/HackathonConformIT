# builders.py
import json
from typing import List, Dict

from langchain_core.documents import Document

from config import logger

class SchemaDocumentBuilder:
    """Builds rich documents from schema with synonyms and descriptions"""
    
    @staticmethod
    def build_documents(schema: Dict) -> List[Document]:
        docs = []
        texts_elements = []
        # 1. Table documents with enriched metadata
        for table_name, table_info in schema.get("tables", {}).items():
            columns_details = []
            all_synonyms = []
            
            for col in table_info.get("columns", []):
                col_text = f"{col['name']} ({col['type']})"
                
                # Add description if available
                if col.get("description"):
                    col_text += f" - {col['description']}"
                
                # Add synonyms
                synonyms = col.get("synonyms", [])
                if synonyms:
                    col_text += f" [synonymes: {', '.join(synonyms[:3])}]"
                    all_synonyms.extend(synonyms)
                
                columns_details.append(col_text)
                if col['type'] == "TEXT":
                    texts_elements.append("")
            # Main table document with full context
            content = f"""Table: {table_name}
            Description: {table_info.get('description', 'Pas de description')}

            Colonnes:
            {chr(10).join(f"  - {cd}" for cd in columns_details)}

            Synonymes de colonnes: {', '.join(all_synonyms[:15]) if all_synonyms else 'Aucun'}"""            
            docs.append(Document(
                page_content=content,
                metadata={
                    "type": "table",
                    "table_name": table_name,
                    "column_count": len(table_info.get("columns", []))
                }
            ))
            
            # Individual column documents for better granularity
            for col in table_info.get("columns", []):
                if col.get("synonyms") or col.get("description"):
                    col_content = f"Colonne {col['name']} dans la table {table_name}\n"
                    col_content += f"Type: {col['type']}\n"
                    
                    if col.get("description"):
                        col_content += f"Description: {col['description']}\n"
                    
                    if col.get("synonyms"):
                        col_content += f"Synonymes: {', '.join(col['synonyms'])}"
                    
                    docs.append(Document(
                        page_content=col_content,
                        metadata={
                            "type": "column",
                            "table_name": table_name,
                            "column_name": col['name']
                        }
                    ))
        
        # 2. Relationship documents with descriptions
        for rel in schema.get("relationships", []):
            content = f"""Relation: {rel['from']} -> {rel['to']}
Type: {rel.get('type', 'foreign_key')}
Condition de jointure: {rel['from']}.{rel['on']} = {rel['to']}.{rel['on']}
Description: {rel.get('description', 'Clé étrangère standard')}"""
            
            docs.append(Document(
                page_content=content,
                metadata={
                    "type": "relationship",
                    "from_table": rel['from'],
                    "to_table": rel['to']
                }
            ))
        
        # 3. Sample query documents (few-shot examples) - MOST IMPORTANT
        for sq in schema.get("sample_queries", []):
            content = f"""EXEMPLE DE REQUÊTE:
Question en langage naturel: {sq['natural_language']}
Requête SQL correspondante:
{sq['sql']}"""
            
            docs.append(Document(
                page_content=content,
                metadata={
                    "type": "example",
                    "language": "sql",
                    "priority": "high" 
                }
            ))
        
        logger.info(f"Built {len(docs)} documents from schema")
        return docs