# sql_generator.py
from typing import Tuple
import re
import json

from langchain_core.prompts import PromptTemplate
from langchain_community.utilities import SQLDatabase
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

from .config import Config, debug_print
from .validators import SQLValidator
from .bedrock_utils import invoke_llm, invoke_embedding

class SQLGenerator:
    """Handles SQL query generation, validation, and execution."""
    
    def __init__(self, db_uri: str):
        self.db = SQLDatabase.from_uri(db_uri)
        self.chat_history = ChatMessageHistory()
        self.prompt = self._build_prompt()
    
    def _build_prompt(self) -> PromptTemplate:
        """Build enhanced prompt template with examples"""
        template = """Tu es un expert SQL PostgreSQL. Génère UNE SEULE requête SQL valide basée sur le contexte fourni.

RÈGLES STRICTES:
1. Réponds UNIQUEMENT avec du code SQL PostgreSQL valide
2. AUCUN texte explicatif avant ou après le SQL
3. Utilise UNIQUEMENT des SELECT (pas de INSERT/UPDATE/DELETE)
4. Utilise les noms de colonnes et tables EXACTS du schéma
5. Ajoute toujours LIMIT 100 si non spécifié par l'utilisateur
6. Pour les dates: format TIMESTAMP '2024-01-01 00:00:00' ou utilise EXTRACT(YEAR FROM colonne)
7. Pour les Jointures: utilise explicitement JOIN ... ON ...
8. Les noms de tables: person, event, organizational_unit, corrective_measure, risk, event_employee, event_risk, event_corrective_measure
9. Pour les recherches sémantiques (similitude de sens), utilise les colonnes d'embedding avec l'opérateur <-> pour la distance cosine et le placeholder <query_embedding> pour le vecteur de la requête. Exemple: ORDER BY description_embedding <-> <query_embedding> ASC
10. Utilise LIKE ou ILIKE pour les recherches par mots-clés exacts, mais <-> pour les recherches sémantiques.

CONTEXTE DE LA BASE DE DONNÉES:
{context}

QUESTION DE L'UTILISATEUR:
{question}

GÉNÈRE MAINTENANT LA REQUÊTE SQL (uniquement le code, rien d'autre):"""
        
        return PromptTemplate.from_template(template)
    
    def _format_chat_history(self) -> str:
        """Format chat history for prompt"""
        if not self.chat_history.messages:
            return "Aucun historique"
        
        history = []
        for msg in self.chat_history.messages[-4:]:  # Last 4 messages
            if isinstance(msg, HumanMessage):
                history.append(f"User: {msg.content[:100]}")
            elif isinstance(msg, AIMessage):
                content = msg.content
                if "SQL:" in content:
                    sql_part = content.split("SQL:")[1].split("Result:")[0].strip()
                    history.append(f"Assistant SQL: {sql_part[:150]}")
        
        return "\n".join(history) if history else "Aucun historique"
    
    def generate_and_execute(self, question: str, context: str) -> Tuple[str, str]:
        """Generate SQL and execute with retry on errors."""
        query_emb = str(invoke_embedding(question))
        
        # Generate initial SQL
        full_prompt = self.prompt.format(
            context=context,
            question=question  # Removed chat_history as it's not in prompt template; can add if needed
        )
        
        sql = invoke_llm(full_prompt)
        sql = SQLValidator.extract_sql(sql)
        sql = sql.replace('<query_embedding>', query_emb)
        
        debug_print(f"Generated SQL:\n{sql}")
        debug_print(f"SQL query for execution:\n{sql}")  # Added debug for SQL query
        # Attempt to auto-fix common mismatches between FK names and PK names
        try:
            fixed_sql = self._auto_fix_sql_columns(sql)
            if fixed_sql != sql:
                debug_print("🔧 SQL auto-fix applied:")
                debug_print(fixed_sql)
                sql = fixed_sql
        except Exception as e:
            debug_print(f"⚠️ Auto-fix SQL step failed: {e}")
        
        # Retry loop
        for attempt in range(Config.MAX_SQL_RETRIES):
            # Validate SQL
            is_safe, error_msg = SQLValidator.is_safe(sql)
            if not is_safe:
                raise ValueError(f"Unsafe SQL detected: {error_msg}")
            
            # Execute
            try:
                result = self.db.run(sql)
                debug_print(f"SQL executed successfully on attempt {attempt + 1}")
                debug_print(f"DB vector search and SQL output result:\n{result}")  # Added debug logging for SQL execution result (includes vector search if used)
                return sql, result
            
            except Exception as exc:
                debug_print(f"Attempt {attempt + 1} failed: {exc}")
                continue
                
                if attempt == Config.MAX_SQL_RETRIES - 1:
                    raise RuntimeError(f"SQL failed after {Config.MAX_SQL_RETRIES} attempts: {exc}")
                
                # Generate corrected SQL
                fix_prompt = f"""La requête SQL PostgreSQL suivante a provoqué une erreur. Corrige-la.

ERREUR EXACTE:
{exc}

SQL ORIGINAL QUI A ÉCHOUÉ:
{sql}

QUESTION UTILISATEUR:
{question}

SCHÉMA DE BASE DE DONNÉES:
{context[:1000]}

INSTRUCTIONS:
- Réponds UNIQUEMENT avec le SQL corrigé
- Vérifie les noms de colonnes et tables
- Vérifie la syntaxe PostgreSQL
- Pas d'explication, juste le code SQL
- Pour les recherches sémantiques, utilise <query_embedding> si nécessaire

SQL CORRIGÉ:"""
                
                corrected = invoke_llm(fix_prompt)
                sql = SQLValidator.extract_sql(corrected)
                sql = sql.replace('<query_embedding>', query_emb)
                debug_print(f"Corrected SQL (attempt {attempt + 2}):\n{sql}")
                debug_print(f"Corrected SQL query:\n{sql}")  # Added debug for corrected SQL
        
        raise RuntimeError("Should not reach here")

    def _auto_fix_sql_columns(self, sql: str) -> str:
        """Auto-fix SQL column references based on schema.json.

        Heuristic: when the SQL references alias.column and the column does not exist
        in the corresponding table (based on schema.json), replace it with the
        table's primary key (first column listed in the schema). This fixes
        common cases where FK in the source table is named like X_id while the
        target table primary key has a different name (e.g. unit_id).
        """
        # Load schema
        try:
            with open(Config.SCHEMA_PATH, 'r', encoding='utf-8') as f:
                schema = json.load(f)
        except Exception:
            return sql

        table_columns = {
            t: {c['name'] for c in info.get('columns', [])}
            for t, info in schema.get('tables', {}).items()
        }
        pk_map = {
            t: (info.get('columns', [])[0]['name'] if info.get('columns') else None)
            for t, info in schema.get('tables', {}).items()
        }

        # Build alias -> table mapping from FROM/JOIN clauses
        alias_map = {}
        for m in re.finditer(r"(?:FROM|JOIN)\s+([a-zA-Z_][\w]*)\s+([a-zA-Z_][\w]*)", sql, flags=re.IGNORECASE):
            tbl, alias = m.group(1), m.group(2)
            alias_map[alias] = tbl

        # Replace alias.column where column not in table columns with alias.<pk>
        def repl(m):
            alias, col = m.group(1), m.group(2)
            tbl = alias_map.get(alias)
            if not tbl:
                return m.group(0)
            cols = table_columns.get(tbl)
            if cols is None:
                return m.group(0)
            if col in cols:
                return m.group(0)
            pk = pk_map.get(tbl)
            if not pk:
                return m.group(0)
            debug_print(f"🔧 Remplacement automatique: {alias}.{col} -> {alias}.{pk}")
            return f"{alias}.{pk}"

        new_sql = re.sub(r"(\b[a-zA-Z_]\w*\b)\.(\b[a-zA-Z_]\w*\b)", repl, sql)
        return new_sql
    
    def update_history(self, question: str, sql: str, result: str):
        """Update chat history."""
        self.chat_history.add_user_message(question)
        self.chat_history.add_ai_message(f"SQL: {sql}\nResult: {result[:200]}")
    
    def clear_history(self):
        """Clear chat history."""
        self.chat_history.clear()