"""
NeuroscribeAI - Redis Caching Service
High-performance caching for extracted facts, validation reports, and queries
"""

import logging
import json
import hashlib
from typing import List, Dict, Optional, Any
from datetime import timedelta
import redis
from redis import Redis, RedisError

from app.config import settings
from app.schemas import AtomicClinicalFact, ValidationReport

logger = logging.getLogger(__name__)


# =============================================================================
# Redis Cache Service
# =============================================================================

class RedisCacheService:
    """Service for caching frequently accessed data"""

    def __init__(self):
        """Initialize Redis connection"""
        self.redis_client: Optional[Redis] = None
        self.default_ttl = settings.cache_ttl  # Default: 3600 seconds (1 hour)
        self.max_size = settings.cache_max_size  # Max entries before eviction

        self._connect()

    def _connect(self):
        """Establish Redis connection"""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                max_connections=settings.redis_max_connections,
                socket_connect_timeout=5,
                socket_timeout=5
            )

            # Test connection
            self.redis_client.ping()
            logger.info(f"✓ Redis cache connected: {settings.redis_url}")

        except RedisError as e:
            logger.error(f"Redis connection failed: {e}")
            logger.warning("Caching will be disabled")
            self.redis_client = None
        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {e}")
            self.redis_client = None

    def _is_available(self) -> bool:
        """Check if Redis is available"""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except:
            return False

    # =========================================================================
    # Key Generation
    # =========================================================================

    def _generate_key(self, prefix: str, *identifiers: Any) -> str:
        """Generate cache key from prefix and identifiers"""
        # Create consistent key: prefix:id1:id2:...
        parts = [prefix] + [str(i) for i in identifiers]
        return ":".join(parts)

    def _hash_key(self, data: str) -> str:
        """Generate hash for complex data (e.g., query strings)"""
        return hashlib.md5(data.encode()).hexdigest()

    # =========================================================================
    # Extraction Results Caching
    # =========================================================================

    def cache_extracted_facts(
        self,
        document_id: int,
        facts: List[AtomicClinicalFact],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache extracted facts for a document

        Args:
            document_id: Document ID
            facts: Extracted facts
            ttl: Time-to-live in seconds (default: 1 hour)

        Returns:
            True if cached successfully
        """
        if not self._is_available():
            return False

        try:
            key = self._generate_key("extraction", document_id)
            value = json.dumps([f.dict() for f in facts])

            self.redis_client.setex(
                key,
                ttl or self.default_ttl,
                value
            )

            logger.info(f"✓ Cached {len(facts)} facts for document {document_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cache facts: {e}")
            return False

    def get_cached_facts(self, document_id: int) -> Optional[List[Dict]]:
        """
        Retrieve cached extracted facts

        Args:
            document_id: Document ID

        Returns:
            List of facts if cached, None otherwise
        """
        if not self._is_available():
            return None

        try:
            key = self._generate_key("extraction", document_id)
            cached = self.redis_client.get(key)

            if cached:
                facts = json.loads(cached)
                logger.info(f"✓ Cache HIT: Retrieved {len(facts)} facts for document {document_id}")
                return facts
            else:
                logger.debug(f"Cache MISS: No cached facts for document {document_id}")
                return None

        except Exception as e:
            logger.error(f"Error retrieving cached facts: {e}")
            return None

    # =========================================================================
    # Validation Report Caching
    # =========================================================================

    def cache_validation_report(
        self,
        patient_id: int,
        report: ValidationReport,
        ttl: Optional[int] = None
    ) -> bool:
        """Cache validation report for a patient"""
        if not self._is_available():
            return False

        try:
            key = self._generate_key("validation", patient_id)
            value = report.json()

            self.redis_client.setex(
                key,
                ttl or self.default_ttl,
                value
            )

            logger.info(f"✓ Cached validation report for patient {patient_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cache validation report: {e}")
            return False

    def get_cached_validation(self, patient_id: int) -> Optional[Dict]:
        """Retrieve cached validation report"""
        if not self._is_available():
            return None

        try:
            key = self._generate_key("validation", patient_id)
            cached = self.redis_client.get(key)

            if cached:
                logger.info(f"✓ Cache HIT: Validation report for patient {patient_id}")
                return json.loads(cached)
            else:
                logger.debug(f"Cache MISS: No cached validation for patient {patient_id}")
                return None

        except Exception as e:
            logger.error(f"Error retrieving cached validation: {e}")
            return None

    # =========================================================================
    # Timeline Caching
    # =========================================================================

    def cache_timeline(
        self,
        patient_id: int,
        timeline: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Cache patient timeline"""
        if not self._is_available():
            return False

        try:
            key = self._generate_key("timeline", patient_id)
            value = json.dumps(timeline)

            self.redis_client.setex(
                key,
                ttl or self.default_ttl,
                value
            )

            logger.info(f"✓ Cached timeline for patient {patient_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cache timeline: {e}")
            return False

    def get_cached_timeline(self, patient_id: int) -> Optional[Dict]:
        """Retrieve cached timeline"""
        if not self._is_available():
            return None

        try:
            key = self._generate_key("timeline", patient_id)
            cached = self.redis_client.get(key)

            if cached:
                logger.info(f"✓ Cache HIT: Timeline for patient {patient_id}")
                return json.loads(cached)
            else:
                logger.debug(f"Cache MISS: No cached timeline for patient {patient_id}")
                return None

        except Exception as e:
            logger.error(f"Error retrieving cached timeline: {e}")
            return None

    # =========================================================================
    # Query Result Caching
    # =========================================================================

    def cache_query_result(
        self,
        query_hash: str,
        results: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Cache query results (for complex searches)"""
        if not self._is_available():
            return False

        try:
            key = self._generate_key("query", query_hash)
            value = json.dumps(results)

            self.redis_client.setex(
                key,
                ttl or self.default_ttl,
                value
            )

            logger.info(f"✓ Cached query result: {query_hash[:16]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to cache query result: {e}")
            return False

    def get_cached_query_result(self, query_hash: str) -> Optional[Any]:
        """Retrieve cached query result"""
        if not self._is_available():
            return None

        try:
            key = self._generate_key("query", query_hash)
            cached = self.redis_client.get(key)

            if cached:
                logger.info(f"✓ Cache HIT: Query {query_hash[:16]}...")
                return json.loads(cached)
            else:
                logger.debug(f"Cache MISS: Query {query_hash[:16]}...")
                return None

        except Exception as e:
            logger.error(f"Error retrieving cached query: {e}")
            return None

    # =========================================================================
    # LLM Response Caching
    # =========================================================================

    def cache_llm_response(
        self,
        prompt_hash: str,
        response: str,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache LLM API responses to reduce costs

        Args:
            prompt_hash: Hash of the prompt
            response: LLM response
            ttl: Cache duration (default: 24 hours for LLM)

        Returns:
            True if cached
        """
        if not self._is_available():
            return False

        try:
            key = self._generate_key("llm", prompt_hash)
            # LLM responses cached longer (24 hours) to save costs
            llm_ttl = ttl or (self.default_ttl * 24)

            self.redis_client.setex(key, llm_ttl, response)

            logger.info(f"✓ Cached LLM response (saves API call): {prompt_hash[:16]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to cache LLM response: {e}")
            return False

    def get_cached_llm_response(self, prompt_hash: str) -> Optional[str]:
        """Retrieve cached LLM response"""
        if not self._is_available():
            return None

        try:
            key = self._generate_key("llm", prompt_hash)
            cached = self.redis_client.get(key)

            if cached:
                logger.info(f"✓ Cache HIT: LLM response (API call saved): {prompt_hash[:16]}...")
                return cached
            else:
                logger.debug(f"Cache MISS: LLM {prompt_hash[:16]}...")
                return None

        except Exception as e:
            logger.error(f"Error retrieving cached LLM response: {e}")
            return None

    def generate_prompt_hash(self, prompt: str, model: str) -> str:
        """Generate hash for LLM prompt (for caching)"""
        combined = f"{model}:{prompt}"
        return self._hash_key(combined)

    # =========================================================================
    # Cache Invalidation
    # =========================================================================

    def invalidate_document_cache(self, document_id: int) -> int:
        """Invalidate all cache entries for a document"""
        if not self._is_available():
            return 0

        try:
            keys_to_delete = [
                self._generate_key("extraction", document_id),
            ]

            deleted = self.redis_client.delete(*keys_to_delete)
            logger.info(f"✓ Invalidated {deleted} cache entries for document {document_id}")
            return deleted

        except Exception as e:
            logger.error(f"Failed to invalidate document cache: {e}")
            return 0

    def invalidate_patient_cache(self, patient_id: int) -> int:
        """Invalidate all cache entries for a patient"""
        if not self._is_available():
            return 0

        try:
            keys_to_delete = [
                self._generate_key("validation", patient_id),
                self._generate_key("timeline", patient_id),
            ]

            deleted = self.redis_client.delete(*keys_to_delete)
            logger.info(f"✓ Invalidated {deleted} cache entries for patient {patient_id}")
            return deleted

        except Exception as e:
            logger.error(f"Failed to invalidate patient cache: {e}")
            return 0

    def clear_all_cache(self) -> bool:
        """Clear entire cache (use with caution!)"""
        if not self._is_available():
            return False

        try:
            self.redis_client.flushdb()
            logger.warning("⚠ Entire cache cleared!")
            return True

        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False

    # =========================================================================
    # Cache Statistics
    # =========================================================================

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics and metrics"""
        if not self._is_available():
            return {"status": "unavailable"}

        try:
            info = self.redis_client.info("stats")

            # Count keys by prefix
            extraction_keys = len(self.redis_client.keys("extraction:*"))
            validation_keys = len(self.redis_client.keys("validation:*"))
            timeline_keys = len(self.redis_client.keys("timeline:*"))
            llm_keys = len(self.redis_client.keys("llm:*"))
            query_keys = len(self.redis_client.keys("query:*"))

            return {
                "status": "available",
                "total_keys": self.redis_client.dbsize(),
                "keys_by_type": {
                    "extraction": extraction_keys,
                    "validation": validation_keys,
                    "timeline": timeline_keys,
                    "llm": llm_keys,
                    "query": query_keys
                },
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info),
                "memory_used": info.get("used_memory_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0)
            }

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"status": "error", "message": str(e)}

    def _calculate_hit_rate(self, info: Dict) -> float:
        """Calculate cache hit rate percentage"""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses

        if total == 0:
            return 0.0

        return round((hits / total) * 100, 2)

    # =========================================================================
    # Health Check
    # =========================================================================

    def health_check(self) -> Dict[str, Any]:
        """Check Redis health"""
        try:
            if not self.redis_client:
                return {"status": "disconnected", "available": False}

            # Ping Redis
            response_time_ms = self.redis_client.ping()

            return {
                "status": "healthy",
                "available": True,
                "response_time_ms": response_time_ms if isinstance(response_time_ms, (int, float)) else 1
            }

        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "available": False,
                "error": str(e)
            }


# =============================================================================
# Global Cache Instance
# =============================================================================

# Lazy initialization
_cache_service: Optional[RedisCacheService] = None


def get_cache_service() -> RedisCacheService:
    """Get or create cache service instance"""
    global _cache_service
    if _cache_service is None:
        _cache_service = RedisCacheService()
    return _cache_service


# =============================================================================
# Convenience Functions
# =============================================================================

def cache_facts(document_id: int, facts: List[AtomicClinicalFact]) -> bool:
    """Cache extracted facts"""
    service = get_cache_service()
    return service.cache_extracted_facts(document_id, facts)


def get_cached_facts(document_id: int) -> Optional[List[Dict]]:
    """Get cached facts if available"""
    service = get_cache_service()
    return service.get_cached_facts(document_id)


def cache_validation(patient_id: int, report: ValidationReport) -> bool:
    """Cache validation report"""
    service = get_cache_service()
    return service.cache_validation_report(patient_id, report)


def get_cached_validation(patient_id: int) -> Optional[Dict]:
    """Get cached validation report"""
    service = get_cache_service()
    return service.get_cached_validation(patient_id)


def invalidate_cache(patient_id: int = None, document_id: int = None) -> int:
    """Invalidate cache entries"""
    service = get_cache_service()

    if document_id:
        return service.invalidate_document_cache(document_id)
    elif patient_id:
        return service.invalidate_patient_cache(patient_id)
    else:
        return 0
