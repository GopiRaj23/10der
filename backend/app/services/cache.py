"""Redis cache + distributed locks, with a graceful in-memory fallback so the
app keeps working when Redis is unavailable (e.g. bare local dev)."""
import json
import logging
import threading
import time

from ..config import settings

logger = logging.getLogger(__name__)

try:
    import redis as _redis
except ImportError:  # pragma: no cover
    _redis = None


class _MemoryCache:
    def __init__(self):
        self._data: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expires, value = item
            if expires < time.time():
                del self._data[key]
                return None
            return value

    def setex(self, key, ttl, value):
        with self._lock:
            self._data[key] = (time.time() + ttl, value)

    def set(self, key, value, nx=False, ex=None):
        with self._lock:
            if nx and self.get(key) is not None:
                return False
            self._data[key] = (time.time() + (ex or 3600), value)
            return True

    def delete(self, *keys):
        with self._lock:
            for k in keys:
                self._data.pop(k, None)

    def ping(self):
        return True


class Cache:
    def __init__(self):
        self._client = None
        self._memory = _MemoryCache()
        if _redis is not None:
            try:
                client = _redis.Redis.from_url(
                    settings.redis_url, socket_connect_timeout=2, decode_responses=True
                )
                client.ping()
                self._client = client
                logger.info("Connected to Redis at %s", settings.redis_url)
            except Exception as exc:
                logger.warning("Redis unavailable (%s) — using in-memory cache", exc)

    @property
    def backend(self) -> str:
        return "redis" if self._client else "memory"

    def _c(self):
        return self._client or self._memory

    def get_json(self, key: str):
        raw = self._c().get(key)
        return json.loads(raw) if raw else None

    def set_json(self, key: str, value, ttl: int) -> None:
        try:
            self._c().setex(key, ttl, json.dumps(value, default=str))
        except Exception as exc:
            logger.warning("Cache write failed for %s: %s", key, exc)

    def acquire_lock(self, key: str, ttl: int = 300) -> bool:
        """Best-effort distributed lock (NX SET). True if acquired."""
        try:
            return bool(self._c().set(key, "1", nx=True, ex=ttl))
        except Exception:
            return True  # never block scraping on cache failure

    def release_lock(self, key: str) -> None:
        try:
            self._c().delete(key)
        except Exception:
            pass

    def queue_depth(self) -> int:
        """Approximate pending-job indicator for the health dashboard."""
        if not self._client:
            return 0
        try:
            return sum(1 for _ in self._client.scan_iter("scrape:lock:*"))
        except Exception:
            return 0


cache = Cache()
