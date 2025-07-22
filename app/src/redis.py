import redis
from typing import Optional
from redis.lock import Lock

from app.src.constants import (
    REDIS_HOST,
    REDIS_PORT,
    MUTEX_LOCK_TIMEOUT,
    MUTEX_LOCK_MAX_WAIT_TIME,
)

redisClient = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)


def acquireLock(
    tableName: str,
    pk: Optional[int] = None,
    timeOut=MUTEX_LOCK_TIMEOUT,
    blockingTimeout=MUTEX_LOCK_MAX_WAIT_TIME,
) -> Optional[Lock]:
    # Acquire a mutex lock for a table or specific row using Redis, returning the lock object if acquired.
    try:
        if pk is None:
            lockName = f"lock:{tableName}"
        else:
            lockName = f"lock:{tableName}:{pk}"
        lock = redisClient.lock(lockName, timeout=timeOut)
        acquired = lock.acquire(blocking=True, blocking_timeout=blockingTimeout)
        if acquired:
            return lock
        else:
            return None
    except Exception:
        return None


def releaseLock(lock: Lock):
    # Release a previously acquired Redis lock.
    try:
        if lock:
            lock.release()
    except Exception:
        pass
