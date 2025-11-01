# config.py
import os
import logging
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Models
    TITAN_EMBED_MODEL = "amazon.titan-embed-text-v1"
    CLAUDE_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"
    
    # Database
    DB_URI = f"postgresql+psycopg2://postgres:{os.getenv('POSTGRES_PASSWORD','yourpass')}@localhost:5432/events_db"
    
    # Vector Store
    INDEX_DIR = "faiss_index"
    TOP_K_RETRIEVAL = 10
    
    # RAG
    MAX_SQL_RETRIES = 3
    CACHE_TTL = 3600  # 1 hour
    
    # Security
    ALLOWED_SQL_OPERATIONS = ["SELECT"]
    FORBIDDEN_SQL_OPERATIONS = ["DROP", "TRUNCATE", "ALTER", "CREATE", "DELETE", "UPDATE", "INSERT"]
    
    # Vector
    VECTOR_DIM = 1536  # Titan Embeddings v1
    SCHEMA_PATH = "schema.json"
    
    # ============================================
    # PARAMÈTRES D'OPTIMISATION BATCH EMBEDDINGS
    # ============================================
    
    # Taille des batches pour génération d'embeddings
    # Recommandé: 20-100 selon la taille des textes
    EMBEDDING_BATCH_SIZE = 50
    
    # Nombre de workers parallèles pour Bedrock
    # Recommandé: 5-15 (attention aux limites AWS)
    # Plus élevé = plus rapide, mais risque de throttling
    EMBEDDING_MAX_WORKERS = 10
    
    # Délai entre requêtes (secondes) pour éviter rate limiting
    # 0.05 = 20 req/sec, 0.1 = 10 req/sec
    EMBEDDING_DELAY = 0.05
    
    # Nombre de tentatives en cas d'erreur
    EMBEDDING_RETRY_COUNT = 3
    
    # ============================================
    # PROFILS DE PERFORMANCE
    # ============================================
    
    @classmethod
    def set_performance_profile(cls, profile: str):
        """
        Configure les paramètres selon un profil de performance
        
        Profils disponibles:
        - 'fast': Maximum de vitesse (risque de throttling)
        - 'balanced': Équilibré (recommandé)
        - 'safe': Plus lent mais sans risque de throttling
        """
        if profile == 'fast':
            cls.EMBEDDING_BATCH_SIZE = 100
            cls.EMBEDDING_MAX_WORKERS = 20
            cls.EMBEDDING_DELAY = 0.02
            print("⚡ Profil FAST activé: batch=100, workers=20, delay=0.02s")
        
        elif profile == 'balanced':
            cls.EMBEDDING_BATCH_SIZE = 50
            cls.EMBEDDING_MAX_WORKERS = 10
            cls.EMBEDDING_DELAY = 0.05
            print("⚖️  Profil BALANCED activé: batch=50, workers=10, delay=0.05s")
        
        elif profile == 'safe':
            cls.EMBEDDING_BATCH_SIZE = 20
            cls.EMBEDDING_MAX_WORKERS = 5
            cls.EMBEDDING_DELAY = 0.1
            print("🛡️  Profil SAFE activé: batch=20, workers=5, delay=0.1s")
        
        else:
            raise ValueError(f"Profil inconnu: {profile}. Utilisez 'fast', 'balanced', ou 'safe'")

# Logging Setup
logging.basicConfig(
    level=logging.INFO,  # Changed back to INFO for better visibility
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)