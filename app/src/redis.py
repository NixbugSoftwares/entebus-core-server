import redis
from typing import Optional
from redis.lock import Lock

from app.src.constants import REDIS_HOST, REDIS_PORT, LOCK_EXPIRE_LIMIT

redisClient = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)


def acquireLock(
    tableName: str, pk: Optional[int] = None, timeout=LOCK_EXPIRE_LIMIT
) -> Optional[Lock]:
    # Acquire a mutex lock for a table or specific row using Redis, returning the lock object if acquired.
    if pk is None:
        lockName = f"lock:{tableName}"
    else:
        lockName = f"lock:{tableName}:{pk}"
    lock = redisClient.lock(lockName, timeout=timeout)
    acquired = lock.acquire(blocking=True)
    if acquired:
        return lock
    else:
        return None


def releaseLock(lock: Lock):
    # Release a previously acquired Redis lock.
    if lock:
        lock.release()
