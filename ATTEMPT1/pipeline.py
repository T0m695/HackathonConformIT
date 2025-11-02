# pipeline.py (VERSION AVEC RECHERCHE VECTORIELLE TEXT INTÉGRÉE)
import json
import urllib.parse
import psycopg2

from datetime import datetime
from typing import Dict, List, Tuple, Optional

from ATTEMPT1.config import Config, logger
from ATTEMPT1.cache import CacheManager
from ATTEMPT1.vector_store import VectorStoreManager
from ATTEMPT1.sql_generator import SQLGenerator
from ATTEMPT1.bedrock_utils import invoke_embedding
from ATTEMPT1.faiss_text_indexer import FAISSTextIndexer
import re

class EnhancedRAGPipeline:
    """Enhanced RAG pipeline with integrated FAISS text search."""
    
    def __init__(self, schema_path: str = Config.SCHEMA_PATH):
        self.cache = CacheManager(use_redis=False)
        self.vector_manager = VectorStoreManager(schema_path)
        self.sql_generator = SQLGenerator(Config.DB_URI)
        self.text_indexer = FAISSTextIndexer()
        logger.info("RAG Pipeline initialized with integrated FAISS text search")
    
    def _detect_text_search_need(self, question: str) -> Optional[Tuple[str, str]]:
        """
        Détecte si la question nécessite une recherche vectorielle dans les TEXT
        Retourne (table, column) si détecté, None sinon
        """
        question_lower = question.lower()
        
        # Par défaut, chercher dans event.description avec la query et les embeddings FAISS
        return ("event", "description")
    
    def build_text_indexes(self, force: bool = False):
        """Build FAISS text indexes if they don't exist or force is True"""
        if force:
            self.text_indexer.clear_indexes()
        if not self.text_indexer.indexes:
            self.text_indexer.build_faiss_indexes()
            
    def _get_text_search_context(
        self, 
        question: str, 
        table: str, 
        column: str, 
        top_k: int = 5
    ) -> str:
        """Effectue une recherche vectorielle et retourne le contexte formaté"""
        
        # Build indexes if they don't exist
        if not self.text_indexer.indexes:
            logger.warning("FAISS indexes not found, building them first...")
            self.build_text_indexes()
        
        try:
            results = self.text_indexer.search(question, table, column, top_k)
            
            if not results:
                return ""
            
            context_parts = [
                f"\n{'='*70}",
                f"🔍 CONTEXTE DE RECHERCHE VECTORIELLE (Table: {table}, Colonne: {column})",
                f"{'='*70}",
                f"\nTextes similaires trouvés dans la base de données:\n"
            ]
            
            for i, result in enumerate(results, 1):
                similarity_percent = result['similarity'] * 100
                text_preview = result['text'][:200] + "..." if len(result['text']) > 200 else result['text']
                
                context_parts.append(
                    f"\n[Résultat #{i} - Similarité: {similarity_percent:.1f}%]\n"
                    f"{text_preview}\n"
                )
            
            context_parts.append(
                f"\n{'='*70}\n"
                f"💡 Utilise ces exemples pour comprendre le contexte de la question.\n"
                f"{'='*70}\n"
            )
            
            return "\n".join(context_parts)
        
        except Exception as e:
            logger.warning(f"Text search failed: {e}")
            return ""
    
    def ask(self, question: str) -> Dict:
        """Main query method with integrated text search"""
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
                    "execution_time": 0,
                    "used_text_search": False
                }
            
            # 1. Retrieve schema context (always)


            question = re.sub(r'\bincidents?\b', 'problème', question, flags=re.IGNORECASE)
            schema_context = self.vector_manager.retrieve_context(question)
            schema_context = re.sub(r'"description":\s*".*?"(,)?', '', schema_context)

            # 2. Check if text search is needed
            text_search_target = self._detect_text_search_need(question)
            text_search_context = ""
            used_text_search = False
            
            if text_search_target:
                table, column = text_search_target
                key = f"{table}.{column}"
                
                # Vérifier que l'index existe
                if key in self.text_indexer.get_indexed_columns():
                    print(f"\n🔍 Recherche vectorielle détectée pour: {table}.{column}")
                    text_search_context = self._get_text_search_context(
                        question, table, column, top_k=5
                    )
                    used_text_search = True
                    print(text_search_context)
                else:
                    print(f"\n⚠️  Index FAISS non trouvé pour {key}. Exécutez 'build_faiss_indexes' d'abord.")
            
            # 3. Combine contexts
            full_context = schema_context
            if text_search_context:
                full_context = f"{schema_context}\n\n{text_search_context}"
            
            # 4. Generate and execute SQL
            sql, result = self.sql_generator.generate_and_execute(question, full_context)
            
            # Cache result
            self.cache.set(question, result)
            
            # Update chat history
            self.sql_generator.update_history(question, sql, result)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "success": True,
                "question": question,
                "sql": sql,
                "result": result,
                "from_cache": False,
                "execution_time": execution_time,
                "used_text_search": used_text_search
            }
        
        except Exception as e:
            logger.error(f"Query failed: {e}", exc_info=True)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "success": False,
                "question": question,
                "error": str(e),
                "execution_time": execution_time,
                "used_text_search": False
            }
    
    def rebuild_index(self):
        """Rebuild vector store index (schema)."""
        self.vector_manager.rebuild()
    
    def clear_cache_and_history(self):
        """Clear cache and history."""
        self.cache.clear()
        self.sql_generator.clear_history()
    
    def _get_db_connection(self):
        """Get psycopg2 connection from DB_URI."""
        parsed = urllib.parse.urlparse(Config.DB_URI)
        userpass = parsed.netloc.split('@')[0]
        hostport = parsed.netloc.split('@')[1]
        user, password = userpass.split(':') if ':' in userpass else (userpass, '')
        host, port = hostport.split(':') if ':' in hostport else (hostport, '5432')
        dbname = parsed.path.lstrip('/')
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        return conn
    
    def build_faiss_indexes(self):
        """Construit les index FAISS pour toutes les colonnes TEXT"""
        print("\n🔨 Construction RAPIDE des index FAISS pour les colonnes TEXT...")
        print(f"⚡ Configuration actuelle:")
        print(f"   • Batch size: {Config.EMBEDDING_BATCH_SIZE}")
        print(f"   • Workers parallèles: {Config.EMBEDDING_MAX_WORKERS}")
        print(f"   • Délai entre requêtes: {Config.EMBEDDING_DELAY}s")
        print(f"   • Retry count: {Config.EMBEDDING_RETRY_COUNT}")
        
        self.text_indexer.build_all_indexes(
            batch_size=Config.EMBEDDING_BATCH_SIZE,
            max_workers=Config.EMBEDDING_MAX_WORKERS
        )
        print("\n✅ Index FAISS construits avec succès!")
    
    def search_in_text(self, query: str, table: str = "event", column: str = "description", top_k: int = 5) -> Dict:
        """Recherche vectorielle directe dans les champs TEXT avec FAISS"""
        start_time = datetime.now()
        
        try:
            print(f"\n🔍 Recherche vectorielle FAISS dans {table}.{column}...")
            print(f"   Question: {query}")
            print(f"   Top-K: {top_k}")
            
            results = self.text_indexer.search(query, table, column, top_k)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            print(f"\n✅ {len(results)} résultats trouvés en {execution_time:.2f}s")
            
            return {
                "success": True,
                "query": query,
                "table": table,
                "column": column,
                "results": results,
                "count": len(results),
                "execution_time": execution_time
            }
        
        except Exception as e:
            logger.error(f"FAISS search failed: {e}", exc_info=True)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "success": False,
                "query": query,
                "error": str(e),
                "execution_time": execution_time
            }
    
    def get_faiss_stats(self):
        """Affiche les statistiques des index FAISS"""
        stats = self.text_indexer.get_index_stats()
        indexed_cols = self.text_indexer.get_indexed_columns()
        
        print("\n📊 STATISTIQUES DES INDEX FAISS")
        print("="*70)
        
        if not indexed_cols:
            print("❌ Aucun index FAISS trouvé. Exécutez 'build_faiss_indexes' d'abord.")
            return
        
        print(f"\n📁 Colonnes indexées: {len(indexed_cols)}")
        
        for col_key in indexed_cols:
            stat = stats[col_key]
            print(f"\n🔸 {col_key}")
            print(f"   • Nombre de vecteurs: {stat['num_vectors']}")
            print(f"   • Dimension: {stat['dimension']}")
            print(f"   • Textes indexés: {stat['num_texts']}")
        
        print("\n" + "="*70)
    
    # Méthodes de compatibilité
    def init_vectors(self):
        """Pas nécessaire avec FAISS - les embeddings sont stockés dans l'index"""
        print("\n✅ Avec FAISS, pas besoin d'initialiser des colonnes dans la base.")
        print("   Les embeddings sont stockés directement dans l'index FAISS.")
        print("\n💡 Utilisez 'build_faiss_indexes' pour créer les index.")
    
    def populate_vectors(self, batch_size: int = 100):
        """Alias pour build_faiss_indexes"""
        print("\n📚 Redirection vers build_faiss_indexes...")
        self.build_faiss_indexes()