# faiss_text_indexer.py (VERSION OPTIMISÉE AVEC BATCH)
import os
import json
import pickle
import shutil
import urllib.parse
import psycopg2
import numpy as np
import faiss

from typing import List, Dict, Tuple, Optional
from ATTEMPT1.config import Config, logger
from ATTEMPT1.bedrock_utils import invoke_embedding, invoke_embeddings_batch

class FAISSTextIndexer:
    """Gère les index FAISS pour les champs TEXT de la base de données (VERSION OPTIMISÉE)"""
    
    def __init__(self, index_base_dir: str = "faiss_text_indexes"):
        self.index_base_dir = index_base_dir
        self.indexes: Dict[str, Dict] = {}
        self.query_cache: Dict[str, np.ndarray] = {}  # Cache for query embeddings
        os.makedirs(index_base_dir, exist_ok=True)
        
        # Try to load existing indexes first
        if not self._load_indexes():
            logger.warning("No pre-built FAISS indexes found, you may want to call build_faiss_indexes()")
            
        # Load query cache if it exists
        self._load_query_cache()
    
    def _get_db_connection(self):
        """Get psycopg2 connection from DB_URI."""
        parsed = urllib.parse.urlparse(Config.DB_URI)
        userpass = parsed.netloc.split('@')[0]
        hostport = parsed.netloc.split('@')[1]
        user, password = userpass.split(':') if ':' in userpass else (userpass, '')
        host, port = hostport.split(':') if ':' in hostport else (hostport, '5432')
        dbname = parsed.path.lstrip('/')
        
        return psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
    
    def _get_index_path(self, table: str, column: str) -> str:
        return os.path.join(self.index_base_dir, f"{table}_{column}.index")
    
    def _get_metadata_path(self, table: str, column: str) -> str:
        return os.path.join(self.index_base_dir, f"{table}_{column}_metadata.pkl")
    
    def _get_query_cache_path(self) -> str:
        return os.path.join(self.index_base_dir, "query_cache.pkl")
        
    def _load_query_cache(self):
        """Load query embedding cache from disk"""
        cache_path = self._get_query_cache_path()
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    self.query_cache = pickle.load(f)
                logger.info(f"Loaded {len(self.query_cache)} cached query embeddings")
            except Exception as e:
                logger.error(f"Failed to load query cache: {e}")
                self.query_cache = {}
                
    def _save_query_cache(self):
        """Save query embedding cache to disk"""
        cache_path = self._get_query_cache_path()
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(self.query_cache, f)
            logger.info(f"Saved {len(self.query_cache)} query embeddings to cache")
        except Exception as e:
            logger.error(f"Failed to save query cache: {e}")
    
    def _load_indexes(self) -> bool:
        """Charge tous les index FAISS existants. Retourne True si au moins un index a été chargé."""
        if not os.path.exists(self.index_base_dir):
            return False
            
        found_any = False
        
        for filename in os.listdir(self.index_base_dir):
            if filename.endswith('.index'):
                base_name = filename.replace('.index', '')
                parts = base_name.split('_')
                
                if len(parts) >= 2:
                    table = parts[0]
                    column = '_'.join(parts[1:])
                    
                    try:
                        index_path = self._get_index_path(table, column)
                        metadata_path = self._get_metadata_path(table, column)
                        
                        if os.path.exists(index_path) and os.path.exists(metadata_path):
                            index = faiss.read_index(index_path)
                            with open(metadata_path, 'rb') as f:
                                metadata = pickle.load(f)
                            
                            key = f"{table}.{column}"
                            self.indexes[key] = {
                                'index': index,
                                'metadata': metadata,
                                'table': table,
                                'column': column
                            }
                            logger.info(f"Loaded FAISS index: {key} ({index.ntotal} vectors)")
                            found_any = True
                    except Exception as e:
                        logger.error(f"Failed to load index {base_name}: {e}")
        
        return found_any
    
    def clear_indexes(self):
        """Clear all FAISS indexes and rebuild them"""
        self.indexes.clear()
        if os.path.exists(self.index_base_dir):
            shutil.rmtree(self.index_base_dir)
        os.makedirs(self.index_base_dir, exist_ok=True)
    
    def build_index_for_column(
        self, 
        table: str, 
        column: str, 
        batch_size: int = 50,
        max_workers: int = 10
    ):
        """Construit un index FAISS pour une colonne TEXT (VERSION BATCH OPTIMISÉE)"""
        conn = self._get_db_connection()
        try:
            cur = conn.cursor()
            
            print(f"\n🔨 Construction de l'index FAISS pour {table}.{column}...")
            
            # Récupérer tous les textes non-vides
            cur.execute(f"""
                SELECT {column}, ctid
                FROM {table}
                WHERE {column} IS NOT NULL AND {column} != ''
                ORDER BY ctid;
            """)
            
            rows = cur.fetchall()
            total = len(rows)
            
            if total == 0:
                print(f"   ⚠️  Aucun texte trouvé dans {table}.{column}")
                return
            
            print(f"   📊 {total} textes à indexer...")
            print(f"   ⚡ Mode BATCH activé (batch_size={batch_size}, workers={max_workers})")
            
            # Créer l'index FAISS
            dimension = Config.VECTOR_DIM
            index = faiss.IndexFlatIP(dimension)
            
            metadata = []
            all_embeddings = []
            
            # Traitement par batch
            for batch_start in range(0, total, batch_size):
                batch_end = min(batch_start + batch_size, total)
                batch_rows = rows[batch_start:batch_end]
                batch_texts = [text for text, _ in batch_rows]
                
                print(f"   🔄 Batch {batch_start//batch_size + 1}/{(total + batch_size - 1)//batch_size} ({batch_start+1}-{batch_end}/{total})...")
                
                # Générer embeddings en parallèle
                batch_embeddings = invoke_embeddings_batch(
                    batch_texts, 
                    max_workers=max_workers,
                    delay_between_batches=0.05  # Petit délai pour éviter rate limiting
                )
                
                # Traiter les résultats
                for i, (text, ctid) in enumerate(batch_rows):
                    emb = batch_embeddings[i]
                    
                    if emb is None:
                        logger.warning(f"Skipping text at index {batch_start + i} due to embedding failure")
                        continue
                    
                    # Normaliser
                    emb_array = np.array(emb, dtype=np.float32)
                    norm = np.linalg.norm(emb_array)
                    if norm > 0:
                        emb_array = emb_array / norm
                    
                    all_embeddings.append(emb_array)
                    metadata.append({
                        'text': text,
                        'ctid': str(ctid),
                        'index_id': len(metadata)
                    })
            
            if all_embeddings:
                # Ajouter tous les vecteurs à l'index
                embeddings_matrix = np.vstack(all_embeddings)
                index.add(embeddings_matrix)
                
                # Sauvegarder
                index_path = self._get_index_path(table, column)
                metadata_path = self._get_metadata_path(table, column)
                
                faiss.write_index(index, index_path)
                with open(metadata_path, 'wb') as f:
                    pickle.dump(metadata, f)
                
                # Charger dans la mémoire
                key = f"{table}.{column}"
                self.indexes[key] = {
                    'index': index,
                    'metadata': metadata,
                    'table': table,
                    'column': column
                }
                
                print(f"   ✅ Index créé : {len(all_embeddings)} vecteurs indexés")
                logger.info(f"FAISS index built for {table}.{column}: {len(all_embeddings)} vectors")
            else:
                print(f"   ❌ Aucun embedding généré")
        
        finally:
            conn.close()
    
    def build_faiss_indexes(self, batch_size: int = 50, max_workers: int = 5) -> None:
        """Construit les index FAISS pour toutes les colonnes TEXT (OPTIMISÉ)"""
        conn = self._get_db_connection()
        
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE data_type = 'text'
                AND table_schema = 'public'
            """)
            text_columns = cur.fetchall()
            
            print(f"\n📚 Construction RAPIDE des index FAISS pour {len(text_columns)} colonnes TEXT...")
            print(f"⚡ Configuration: batch_size={batch_size}, workers={max_workers}")
            print(f"💡 Astuce: Augmentez 'workers' (10-20) pour plus de vitesse si AWS le permet\n")
            
            for table, column in text_columns:
                self.build_index_for_column(table, column, batch_size, max_workers)
            
            print("\n✅ Tous les index FAISS ont été construits!")
        finally:
            conn.close()
    
    def search(self, query: str, table: str, column: str, top_k: int = 5) -> List[Dict]:
        """Recherche vectorielle avec FAISS"""
        key = f"{table}.{column}"
        
        if key not in self.indexes:
            raise ValueError(f"Aucun index FAISS trouvé pour {key}. Exécutez 'build_faiss_indexes' d'abord.")
        
        index_data = self.indexes[key]
        index = index_data['index']
        metadata = index_data['metadata']
        
        # Try to get embedding from cache first
        if query in self.query_cache:
            query_array = self.query_cache[query]
            logger.info(f"Using cached embedding for query: {query[:50]}...")
        else:
            # Generate new embedding if not in cache
            query_emb = invoke_embedding(query)
            query_array = np.array([query_emb], dtype=np.float32)
            
            # Normalize
            norm = np.linalg.norm(query_array)
            if norm > 0:
                query_array = query_array / norm
                
            # Cache the normalized embedding
            self.query_cache[query] = query_array
            self._save_query_cache()
            logger.info(f"Generated and cached new embedding for query: {query[:50]}...")
        
        # Recherche dans l'index
        distances, indices = index.search(query_array, min(top_k, index.ntotal))
        
        # Formater les résultats
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(metadata):
                meta = metadata[idx]
                similarity = float(distances[0][i])
                
                results.append({
                    'text': meta['text'],
                    'similarity': similarity,
                    'distance': 1 - similarity,
                    'rank': i + 1
                })
        
        return results
    
    def get_indexed_columns(self) -> List[str]:
        return list(self.indexes.keys())
    
    def get_index_stats(self) -> Dict:
        stats = {}
        for key, data in self.indexes.items():
            stats[key] = {
                'num_vectors': data['index'].ntotal,
                'dimension': data['index'].d,
                'num_texts': len(data['metadata'])
            }
        return stats