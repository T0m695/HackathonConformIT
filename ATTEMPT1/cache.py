# cache.py
import hashlib
import re
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import os
from .config import Config, debug_print

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

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
                debug_print("✅ Redis cache connected")
            except redis.ConnectionError as e:
                debug_print(f"⚠️ Redis unavailable, using memory cache: {e}")
    
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
                    debug_print(f"💾 Cache HIT (Redis): {question[:50]}...")
                    return value
            except Exception as e:
                debug_print(f"❌ Redis get error: {e}")
        
        # Fallback to memory cache
        if key in self.memory_cache:
            value, timestamp = self.memory_cache[key]
            if datetime.now() - timestamp < timedelta(seconds=Config.CACHE_TTL):
                debug_print(f"💾 Cache HIT (Memory): {question[:50]}...")
                return value
            else:
                del self.memory_cache[key]
        
        debug_print(f"🔍 Cache MISS: {question[:50]}...")
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
                debug_print(f"❌ Redis set error: {e}")
        
        # Store in memory cache
        self.memory_cache[key] = (result, datetime.now())
    
    def clear(self):
        """Clear cache"""
        self.memory_cache.clear()
        if self.redis_client:
            try:
                for key in self.redis_client.scan_iter("sql_cache:*"):
                    self.redis_client.delete(key)
                debug_print("🧹 Redis cache cleared")
            except Exception as e:
                debug_print(f"❌ Redis clear error: {e}")