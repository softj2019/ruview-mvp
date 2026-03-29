"""
cache_manager.py — Redis 세션 캐싱 (optional, in-memory fallback)

Redis가 없는 환경에서도 동작합니다.
- redis-py 설치 & Redis 서버 가용 시: Redis 백엔드 사용
- 그 외: in-memory dict fallback 사용
"""
import json
import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import redis as redis_lib
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    logger.info("redis-py not installed — using in-memory fallback")


class _InMemoryCache:
    """TTL 지원 in-memory dict 캐시 (Redis 미가용 시 fallback)."""

    def __init__(self):
        self._store: dict[str, tuple[Any, Optional[float]]] = {}

    def set(self, key: str, value: Any, ttl: int = 30) -> None:
        expires_at = time.monotonic() + ttl if ttl > 0 else None
        self._store[key] = (value, expires_at)

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def is_connected(self) -> bool:
        return True  # in-memory는 항상 "연결됨"


class CacheManager:
    """
    Redis 세션 캐시 매니저.

    사용 예:
        c = CacheManager()
        c.set("presence:zone1", {"occupied": True}, ttl=30)
        data = c.get("presence:zone1")   # dict 또는 None
        c.delete("presence:zone1")
        c.is_connected()                 # True / False
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        socket_timeout: float = 1.0,
    ):
        self._backend: _InMemoryCache | "redis_lib.Redis"
        self._use_redis = False

        if _REDIS_AVAILABLE:
            try:
                client = redis_lib.Redis(
                    host=host,
                    port=port,
                    db=db,
                    password=password,
                    socket_timeout=socket_timeout,
                    decode_responses=True,
                )
                client.ping()
                self._backend = client
                self._use_redis = True
                logger.info("CacheManager: Redis 연결 성공 (%s:%d)", host, port)
            except Exception as e:
                logger.warning(
                    "CacheManager: Redis 연결 실패 (%s) — in-memory fallback 사용", e
                )
                self._backend = _InMemoryCache()
        else:
            self._backend = _InMemoryCache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set(self, key: str, value: Any, ttl: int = 30) -> None:
        """값을 JSON 직렬화하여 저장. ttl=0 이면 만료 없음."""
        try:
            serialized = json.dumps(value, ensure_ascii=False)
            if self._use_redis:
                if ttl > 0:
                    self._backend.setex(key, ttl, serialized)
                else:
                    self._backend.set(key, serialized)
            else:
                self._backend.set(key, serialized, ttl=ttl)
        except Exception as e:
            logger.error("CacheManager.set 실패 key=%s: %s", key, e)

    def get(self, key: str) -> Optional[Any]:
        """저장된 값을 JSON 역직렬화하여 반환. 캐시 미스 → None."""
        try:
            if self._use_redis:
                raw = self._backend.get(key)
            else:
                raw = self._backend.get(key)

            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.error("CacheManager.get 실패 key=%s: %s", key, e)
            return None

    def delete(self, key: str) -> None:
        """키 삭제."""
        try:
            if self._use_redis:
                self._backend.delete(key)
            else:
                self._backend.delete(key)
        except Exception as e:
            logger.error("CacheManager.delete 실패 key=%s: %s", key, e)

    def is_connected(self) -> bool:
        """Redis 백엔드 연결 여부 반환."""
        if not self._use_redis:
            return False
        try:
            self._backend.ping()
            return True
        except Exception:
            return False
