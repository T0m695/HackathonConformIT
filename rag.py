#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Enhanced RAG Text-to-SQL for EHS PostgreSQL DB v2
Improvements:
  - Better document chunking with synonyms and descriptions
  - SQL validation and security
  - Persistent cache with Redis
  - Enhanced prompt engineering with examples
  - Structured logging
  - Few-shot learning from sample queries
"""

# --------------------------------------------------------------
# 1. Imports
# --------------------------------------------------------------
from dotenv import load_dotenv
load_dotenv()

import os
import json
import hashlib
import re
import logging
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta

import boto3

from langchain_core.language_models.llms import LLM
from langchain_core.embeddings import Embeddings
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

from langchain_community.vectorstores import FAISS
from langchain_community.utilities import SQLDatabase
from langchain_community.chat_message_histories import ChatMessageHistory

# Optional: Redis for persistent cache
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# --------------------------------------------------------------
# 2. Logging Setup
# --------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------
# 3. Configuration & Constants
# --------------------------------------------------------------
class Config:
    # Models
    TITAN_EMBED_MODEL = "amazon.titan-embed-text-v1"
    CLAUDE_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"
    
    # Database
    DB_URI = f"postgresql+psycopg2://postgres:{os.getenv('POSTGRES_PASSWORD','yourpass')}@localhost:5432/events_db"
    
    # Vector Store
    INDEX_DIR = "faiss_index"
    TOP_K_RETRIEVAL = 10  # Increased to get more examples
    
    # RAG
    MAX_SQL_RETRIES = 3
    CACHE_TTL = 3600  # 1 hour
    
    # Security
    ALLOWED_SQL_OPERATIONS = ["SELECT"]
    FORBIDDEN_SQL_OPERATIONS = ["DROP", "TRUNCATE", "ALTER", "CREATE", "DELETE", "UPDATE", "INSERT"]

# --------------------------------------------------------------
# 4. SQL Validation & Security
# --------------------------------------------------------------
class SQLValidator:
    """Validates and sanitizes SQL queries"""
    
    @staticmethod
    def is_safe(sql: str) -> Tuple[bool, Optional[str]]:
        """Check if SQL is safe to execute"""
        sql_upper = sql.upper().strip()
        
        # Check for forbidden operations
        for keyword in Config.FORBIDDEN_SQL_OPERATIONS:
            # Check if keyword appears as a separate word (not part of another word)
            if re.search(rf'\b{keyword}\b', sql_upper):
                return False, f"Forbidden operation: {keyword}"
        
        # Must start with SELECT or WITH (for CTEs)
        if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
            return False, "Only SELECT queries are allowed"
        
        # Check for suspicious patterns
        dangerous_patterns = [
            r";\s*(DROP|DELETE|TRUNCATE|ALTER)",
            r"--.*(?:DROP|DELETE)",
            r"/\*.*(?:DROP|DELETE).*\*/"
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, sql_upper):
                return False, "Suspicious pattern detected"
        
        return True, None
    
    @staticmethod
    def extract_sql(text: str) -> str:
        """Extract SQL from LLM response"""
        # Remove markdown code blocks
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("sql"):
                    part = part[3:].strip()
                # Check if starts with SELECT or WITH
                if part.upper().startswith(("SELECT", "WITH")):
                    return part
        
        # Find first SELECT or WITH statement
        lines = []
        in_sql = False
        
        for line in text.split("\n"):
            line_clean = line.strip()
            
            if line_clean.upper().startswith(("SELECT", "WITH")):
                in_sql = True
            
            if in_sql:
                # Stop on explanation markers
                stop_markers = [
                    "explication:", "note:", "remarque:",
                    "this query", "this will", "explanation:",
                    "---", "###"
                ]
                if any(marker in line_clean.lower() for marker in stop_markers):
                    break
                lines.append(line)
        
        sql = "\n".join(lines).strip()
        
        # Remove trailing semicolons and clean up
        sql = re.sub(r';\s*$', '', sql)
        
        return sql if sql else text.strip()

# --------------------------------------------------------------
# 5. Enhanced Document Builder with Synonyms & Descriptions
# --------------------------------------------------------------
class SchemaDocumentBuilder:
    """Builds rich documents from schema with synonyms and descriptions"""
    
    @staticmethod
    def build_documents(schema: Dict) -> List[Document]:
        docs = []
        
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
            content = f"""Relation: {rel['from']} → {rel['to']}
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
                    "priority": "high"  # Mark examples as high priority
                }
            ))
        
        logger.info(f"Built {len(docs)} documents from schema")
        return docs

# --------------------------------------------------------------
# 6. Cache Manager (Memory + Optional Redis)
# --------------------------------------------------------------
class CacheManager:
    """Manages query caching with optional Redis backend"""
    
    def __init__(self, use_redis: bool = False):
        self.memory_cache: Dict[str, Tuple[str, datetime]] = {}
        self.redis_client = None
        
        if use_redis and REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(
                    host=os.getenv('REDIS_HOST', 'localhost'),
                    port=int(os.getenv('REDIS_PORT', 6379)),
                    decode_responses=True
                )
                self.redis_client.ping()
                logger.info("Redis cache connected")
            except Exception as e:
                logger.warning(f"Redis unavailable, using memory cache: {e}")
    
    def _normalize_question(self, question: str) -> str:
        """Normalize question for better cache hits"""
        q = question.lower().strip()
        q = re.sub(r'\s+', ' ', q)
        # Remove common variations
        q = re.sub(r'[?!.,;]', '', q)
        return q
    
    def _get_cache_key(self, question: str) -> str:
        """Generate cache key"""
        normalized = self._normalize_question(question)
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def get(self, question: str) -> Optional[str]:
        """Retrieve from cache"""
        key = self._get_cache_key(question)
        
        # Try Redis first
        if self.redis_client:
            try:
                value = self.redis_client.get(f"sql_cache:{key}")
                if value:
                    logger.info(f"Cache HIT (Redis): {question[:50]}...")
                    return value
            except Exception as e:
                logger.error(f"Redis get error: {e}")
        
        # Fallback to memory cache
        if key in self.memory_cache:
            value, timestamp = self.memory_cache[key]
            if datetime.now() - timestamp < timedelta(seconds=Config.CACHE_TTL):
                logger.info(f"Cache HIT (Memory): {question[:50]}...")
                return value
            else:
                del self.memory_cache[key]
        
        logger.info(f"Cache MISS: {question[:50]}...")
        return None
    
    def set(self, question: str, result: str):
        """Store in cache"""
        key = self._get_cache_key(question)
        
        # Store in Redis
        if self.redis_client:
            try:
                self.redis_client.setex(
                    f"sql_cache:{key}",
                    Config.CACHE_TTL,
                    result
                )
            except Exception as e:
                logger.error(f"Redis set error: {e}")
        
        # Store in memory cache
        self.memory_cache[key] = (result, datetime.now())
    
    def clear(self):
        """Clear cache"""
        self.memory_cache.clear()
        if self.redis_client:
            try:
                for key in self.redis_client.scan_iter("sql_cache:*"):
                    self.redis_client.delete(key)
                logger.info("Redis cache cleared")
            except Exception as e:
                logger.error(f"Redis clear error: {e}")

# --------------------------------------------------------------
# 7. Bedrock Wrappers
# --------------------------------------------------------------
def _get_bedrock_client():
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    access = os.getenv("AWS_ACCESS_KEY_ID")
    secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    token = os.getenv("AWS_SESSION_TOKEN")

    if not access or not secret:
        raise RuntimeError("AWS credentials missing in .env")

    cfg = {
        "service_name": "bedrock-runtime",
        "region_name": region,
        "aws_access_key_id": access,
        "aws_secret_access_key": secret,
    }
    if token:
        cfg["aws_session_token"] = token
    return boto3.client(**cfg)


def invoke_llm(prompt: str, model_id: str = Config.CLAUDE_MODEL) -> str:
    try:
        client = _get_bedrock_client()
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "temperature": 0.0,  # Zero temperature for deterministic SQL
            "messages": [{"role": "user", "content": prompt}]
        })
        resp = client.invoke_model(modelId=model_id, body=body)
        out = json.loads(resp["body"].read())
        return out["content"][0]["text"]
    except Exception as e:
        logger.error(f"LLM invocation failed: {e}")
        return f"LLM error: {e}"


def invoke_embedding(text: str, model_id: str = Config.TITAN_EMBED_MODEL) -> List[float]:
    try:
        client = _get_bedrock_client()
        body = json.dumps({"inputText": text})
        resp = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        out = json.loads(resp["body"].read())
        if "embedding" not in out:
            raise ValueError(f"Bad embedding response: {out}")
        return out["embedding"]
    except Exception as e:
        raise RuntimeError(f"Embedding failed: {e}")


class BedrockLLM(LLM):
    def _call(self, prompt: str, stop: Optional[List[str]] = None,
              run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs) -> str:
        return invoke_llm(prompt)

    @property
    def _llm_type(self) -> str:
        return "bedrock_claude"


class BedrockEmbeddings(Embeddings):
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [invoke_embedding(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return invoke_embedding(text)

# --------------------------------------------------------------
# 8. Enhanced RAG Pipeline
# --------------------------------------------------------------
class EnhancedRAGPipeline:
    """Enhanced RAG pipeline with validation and monitoring"""
    
    def __init__(self, schema_path: str = "schema.json"):
        self.schema_path = schema_path
        self.cache = CacheManager(use_redis=REDIS_AVAILABLE)
        self.chat_history = ChatMessageHistory()
        self.embeddings = BedrockEmbeddings()
        
        # Load or build vector store
        self.vectorstore = self._init_vectorstore()
        self.retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": Config.TOP_K_RETRIEVAL}
        )
        
        # Database connection
        self.db = SQLDatabase.from_uri(Config.DB_URI)
        
        # Enhanced prompt
        self.prompt = self._build_prompt()
        
        logger.info("RAG Pipeline initialized")
    
    def _init_vectorstore(self) -> FAISS:
        """Initialize or load vector store"""
        if os.path.isdir(Config.INDEX_DIR):
            logger.info("Loading existing FAISS index...")
            try:
                return FAISS.load_local(
                    folder_path=Config.INDEX_DIR,
                    embeddings=self.embeddings,
                    allow_dangerous_deserialization=True
                )
            except TypeError:
                logger.warning("Using legacy FAISS.load_local (old LangChain version)")
                return FAISS.load_local(
                    folder_path=Config.INDEX_DIR,
                    embeddings=self.embeddings
                )
        else:
            logger.info("Building FAISS index from schema...")
            with open(self.schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
            
            docs = SchemaDocumentBuilder.build_documents(schema)
            vectorstore = FAISS.from_documents(docs, self.embeddings)
            vectorstore.save_local(Config.INDEX_DIR)
            logger.info(f"FAISS index saved to {Config.INDEX_DIR}")
            return vectorstore
    
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
    
    def _execute_with_retry(self, question: str, context: str) -> Tuple[str, str]:
        """Execute SQL with automatic retry on errors"""
        
        # Generate initial SQL
        full_prompt = self.prompt.format(
            context=context,
            chat_history=self._format_chat_history(),
            question=question
        )
        
        sql = invoke_llm(full_prompt)
        sql = SQLValidator.extract_sql(sql)
        
        logger.info(f"Generated SQL:\n{sql}")
        
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
                return sql, result
            
            except Exception as exc:
                logger.warning(f"Attempt {attempt + 1} failed: {exc}")
                
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

SQL CORRIGÉ:"""
                
                corrected = invoke_llm(fix_prompt)
                sql = SQLValidator.extract_sql(corrected)
                logger.info(f"Corrected SQL (attempt {attempt + 2}):\n{sql}")
        
        raise RuntimeError("Should not reach here")
    
    def ask(self, question: str) -> Dict:
        """Main query method with full pipeline"""
        start_time = datetime.now()
        
        try:
            # Check cache
            cached = self.cache.get(question)
            if cached:
                return {
                    "success": True,
                    "question": question,
                    "sql": "CACHED",
                    "result": cached,
                    "from_cache": True,
                    "execution_time": 0
                }
            
            # Retrieve relevant context
            docs = self.retriever.get_relevant_documents(question)
            
            # Prioritize examples, then tables, then relationships
            sorted_docs = sorted(docs, key=lambda d: {
                "example": 0,
                "table": 1,
                "column": 2,
                "relationship": 3
            }.get(d.metadata.get("type", "other"), 4))
            
            context = "\n\n".join([
                f"[{doc.metadata.get('type', 'info').upper()}]\n{doc.page_content}"
                for doc in sorted_docs
            ])
            
            logger.info(f"Retrieved {len(docs)} relevant documents")
            
            # Execute with retry
            sql, result = self._execute_with_retry(question, context)
            
            # Cache result
            self.cache.set(question, result)
            
            # Update chat history
            self.chat_history.add_user_message(question)
            self.chat_history.add_ai_message(f"SQL: {sql}\nResult: {result[:200]}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "success": True,
                "question": question,
                "sql": sql,
                "result": result,
                "from_cache": False,
                "execution_time": execution_time
            }
        
        except Exception as e:
            logger.error(f"Query failed: {e}", exc_info=True)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "success": False,
                "question": question,
                "error": str(e),
                "execution_time": execution_time
            }
    
    def rebuild_index(self):
        """Rebuild FAISS index from schema"""
        logger.info("Rebuilding FAISS index...")
        
        # Remove old index
        if os.path.isdir(Config.INDEX_DIR):
            import shutil
            shutil.rmtree(Config.INDEX_DIR)
        
        # Rebuild
        with open(self.schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        
        docs = SchemaDocumentBuilder.build_documents(schema)
        self.vectorstore = FAISS.from_documents(docs, self.embeddings)
        self.vectorstore.save_local(Config.INDEX_DIR)
        self.retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": Config.TOP_K_RETRIEVAL}
        )
        
        logger.info("Index rebuilt successfully!")

# --------------------------------------------------------------
# 9. CLI Interface
# --------------------------------------------------------------
def main():
    """Interactive CLI"""
    logger.info("Initializing Enhanced RAG Pipeline...")
    
    try:
        pipeline = EnhancedRAGPipeline()
        logger.info("Pipeline ready!")
    except Exception as e:
        logger.error(f"Failed to initialize pipeline: {e}")
        return
    
    print("\n" + "="*70)
    print(" 🚀 Enhanced Text-to-SQL RAG System v2")
    print("="*70)
    print(" Commands:")
    print("   • 'exit' ou 'quit' - Quitter l'application")
    print("   • 'clear' - Effacer l'historique et le cache")
    print("   • 'rebuild' - Reconstruire l'index FAISS")
    print("   • 'stats' - Afficher les statistiques")
    print("="*70 + "\n")
    
    query_count = {"success": 0, "failed": 0, "cached": 0}
    
    while True:
        try:
            question = input("\n🔍 Question: ").strip()
            
            if not question:
                continue
            
            if question.lower() in ['exit', 'quit']:
                print("\n👋 Au revoir!")
                break
            
            if question.lower() == 'clear':
                pipeline.chat_history.clear()
                pipeline.cache.clear()
                query_count = {"success": 0, "failed": 0, "cached": 0}
                print("✅ Historique et cache effacés")
                continue
            
            if question.lower() == 'rebuild':
                pipeline.rebuild_index()
                print("✅ Index FAISS reconstruit")
                continue
            
            if question.lower() == 'stats':
                print(f"\n📊 Statistiques:")
                print(f"   • Requêtes réussies: {query_count['success']}")
                print(f"   • Requêtes échouées: {query_count['failed']}")
                print(f"   • Requêtes du cache: {query_count['cached']}")
                continue
            
            print("\n⏳ Traitement...")
            response = pipeline.ask(question)
            
            if response["success"]:
                if response["from_cache"]:
                    query_count["cached"] += 1
                else:
                    query_count["success"] += 1
                
                print(f"\n✅ SQL généré ({response['execution_time']:.2f}s):")
                print("─" * 70)
                print(response["sql"])
                print("─" * 70)
                print(f"\n📊 Résultat:")
                result_preview = str(response["result"])
                if len(result_preview) > 1000:
                    print(result_preview[:1000] + "\n... (tronqué)")
                else:
                    print(result_preview)
                
                if response["from_cache"]:
                    print("\n💾 (Résultat du cache)")
            else:
                query_count["failed"] += 1
                print(f"\n❌ Erreur: {response['error']}")
        
        except KeyboardInterrupt:
            print("\n\n👋 Interruption détectée. Au revoir!")
            break
        except Exception as e:
            query_count["failed"] += 1
            logger.error(f"Unexpected error: {e}", exc_info=True)
            print(f"\n❌ Erreur inattendue: {e}")

if __name__ == "__main__":
    main()