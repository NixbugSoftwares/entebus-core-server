import redis
from typing import Optional
from redis.lock import Lock

from app.src.constants import REDIS_HOST, REDIS_PORT

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)


def acquireLock(tableName: str, pk: Optional[int] = None) -> Optional[Lock]:
    """
    Acquire a mutex lock for a table or a specific row using Redis.
    Returns the lock object if acquired, else None.
    """
    lockName = f"lock:{tableName}" + (f":{pk}" if pk else "")
    lock = redis_client.lock(lockName)
    acquired = lock.acquire(blocking=True)
    return lock if acquired else None


def releaseLock(lock: Lock):
    """
    Release a previously acquired Redis lock.
    """
    if lock:
        lock.release()
    redis_client.close()
