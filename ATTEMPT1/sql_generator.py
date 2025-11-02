# sql_generator.py
from typing import Tuple

from langchain_core.prompts import PromptTemplate
from langchain_community.utilities import SQLDatabase
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

from ATTEMPT1.config import Config, logger
from ATTEMPT1.validators import SQLValidator
from ATTEMPT1.bedrock_utils import invoke_llm, invoke_embedding

class SQLGenerator:
    """Handles SQL query generation, validation, and execution."""
    
    def __init__(self, db_uri: str):
        self.db = SQLDatabase.from_uri(db_uri)
        self.chat_history = ChatMessageHistory()
        self.prompt = self._build_prompt()
    
    def _build_prompt(self) -> PromptTemplate:
        """Build enhanced prompt template with examples"""
        template = """RÔLE
Tu es un·e data analyst expert·e en SQL PostgreSQL. Ta mission : produire UNE SEULE requête SQL (PostgreSQL) exacte et exécutable à partir des informations ci-dessous.

CE QUE TU REÇOIS
• {context} contient DEUX blocs concaténés :
  1) Contexte Schéma : tables, colonnes (avec descriptions et synonymes), relations et EXEMPLES DE REQUÊTES (few-shot).
  2) CONTEXTE DE RECHERCHE VECTORIELLE : extraits de textes (snippets) retrouvés dans la BDD (p.ex. table=event, colonne=description) classés par similarité.

STRATÉGIE D’UTILISATION DES DEUX CONTEXTES
A) Contexte 1 — Schéma
   - Choisis les noms EXACTS de tables et colonnes à partir du schéma.
   - Utilise les SYNONYMES fournis pour faire correspondre les mots de la question aux bons champs (ex.: “employé” → person.name).
   - Construis les JOINs à partir des RELATIONS indiquées (clés étrangères et conditions de jointure).
   - Si la question ressemble fortement à un des EXEMPLES DE REQUÊTES, inspire-toi de sa structure et adapte uniquement ce qui est nécessaire (filtres, colonnes, LIMIT, etc.).

B) Contexte 2 — Snippets textuels (recherche vectorielle)
   - NE PAS interroger directement ces extraits ; ils servent d’INDICES.
   - EXTRAIS les entités utiles (mots-clés, noms propres, identifiants, dates, unités, etc.) depuis les snippets.
   - Utilise ces entités pour écrire des WHERE précis, par ex.:
       • ... WHERE description ILIKE '%mot_clé%'  (pour mots/phrases exacts)
       • ... WHERE event_id = 123                 (si un ID est déduit)
   
RÈGLES STRICTES (à respecter à la lettre)
1) Réponds UNIQUEMENT avec du SQL PostgreSQL (pas de texte, pas d’explications).
2) Un seul statement, de type SELECT ou WITH uniquement (aucun DDL/DML).
3) Utilise les noms de tables/colonnes EXACTS du schéma ; n’invente rien.
4) Toujours une syntaxe PostgreSQL valide : JOIN ... ON ..., fonctions/date au format PostgreSQL.
5) Si l’utilisateur n’a pas fixé de limite, ajoute LIMIT 100 à la fin.
6) Dates : utilise TIMESTAMP 'YYYY-MM-DD HH:MI:SS' si nécessaire, ou EXTRACT(YEAR FROM colonne) pour filtrer par année.
7) Mots-clés exacts : LIKE/ILIKE '%mot%'.
8) Similarité sémantique : opérateur <-> sur colonnes d’embedding + <query_embedding>; ordonne par similarité croissante (ASC).
9) Pas d’opérations interdites (DROP/ALTER/TRUNCATE/DELETE/UPDATE/INSERT/CREATE, etc.).
10) Préfère des WHERE précis basés sur entités extraites des snippets ; n’introduis pas de conditions non justifiées par {context} ou {question}.
11) Si le besoin implique plusieurs tables, respecte les relations listées pour écrire des JOIN sûrs.

CHECKLIST AVANT DE RÉPONDRE (interne, ne rien imprimer)
- Tables/colonnes existent-elles dans le schéma du Contexte 1 ?
- Les JOIN suivent-ils les relations documentées ?
- Les filtres WHERE sont-ils justifiés par {question} et/ou par les entités extraites du Contexte 2 ?
- LIMIT présent si non spécifié ?

QUESTION UTILISATEUR
{question}

CONTEXTE
{context}

↯ RENDS UNIQUEMENT LA REQUÊTE SQL (aucun texte autour)."""
        
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
        
        logger.info(f"Generated SQL:\n{sql}")
        logger.debug(f"SQL query for execution:\n{sql}")  # Added debug logging for SQL query
        
        # Retry loop
        for attempt in range(Config.MAX_SQL_RETRIES):
            # Validate SQL
            is_safe, error_msg = SQLValidator.is_safe(sql)
            if not is_safe:
                raise ValueError(f"Unsafe SQL detected: {error_msg}")
            
            # Execute
            try:
                result = self.db.run(sql)
                logger.info(f"SQL executed successfully on attempt {attempt + 1}")
                logger.debug(f"DB vector search and SQL output result:\n{result}")  # Added debug logging for SQL execution result (includes vector search if used)
                return sql, result
            
            except Exception as exc:
                logger.warning(f"Attempt {attempt + 1} failed: {exc}")
                
                if attempt == Config.MAX_SQL_RETRIES - 1:
                    raise RuntimeError(f"SQL failed after {Config.MAX_SQL_RETRIES} attempts: {exc}")

    def update_history(self, question: str, sql: str, result: str) -> None:
        """Update chat history with the latest interaction"""
        self.chat_history.add_user_message(question)
        self.chat_history.add_ai_message(f"SQL: {sql}\nResult: {result}")

    def fix_sql_error(self, sql: str, exc: str, question: str, context: str, query_emb: str = "", attempt: int = 0) -> str:
        """Generate a corrected SQL query after an error"""
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
        logger.info(f"Corrected SQL (attempt {attempt + 2}):\n{sql}")
        logger.debug(f"Corrected SQL query:\n{sql}")  # Added debug for corrected SQL
        return sql
    
    def update_history(self, question: str, sql: str, result: str):
        """Update chat history."""
        self.chat_history.add_user_message(question)
        self.chat_history.add_ai_message(f"SQL: {sql}\nResult: {result[:200]}")
    
    def clear_history(self):
        """Clear chat history."""
        self.chat_history.clear()