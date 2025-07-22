import redis
from typing import Optional
from redis.lock import Lock

from app.src.constants import REDIS_HOST, REDIS_PORT

redisClient = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)


def acquireLock(tableName: str, pk: Optional[int] = None) -> Optional[Lock]:
    """
    Acquire a mutex lock for a table or a specific row using Redis.
    Returns the lock object if acquired, else None.
    """
    try:
        if pk is None:
            lockName = f"lock:{tableName}"
        else:
            lockName = f"lock:{tableName}:{pk}"
        lock = redisClient.lock(lockName)
        acquired = lock.acquire(blocking=True)
        if acquired:
            return lock
        else:
            return None
    except Exception:
        print(f"Failed to acquire lock:")


def releaseLock(lock: Lock):
    """
    Release a previously acquired Redis lock.
    """
    try:
        if lock:
            lock.release()
    except Exception:
        print(f"Failed to release lock:")