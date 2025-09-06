from redis import Redis
from typing import Optional
from redis.lock import Lock

from app.src import exceptions
from app.src.constants import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_PASSWORD,
    MUTEX_LOCK_TIMEOUT,
    MUTEX_LOCK_MAX_WAIT_TIME,
)

# Redis client (single connection)
redisClient = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
)


def acquireLock(
    tableName: str,
    pk: Optional[int] = None,
    timeOut: int = MUTEX_LOCK_TIMEOUT,
    blockingTimeOut: int = MUTEX_LOCK_MAX_WAIT_TIME,
) -> Lock:
    """
    Acquire a Redis-based mutex lock for a table or specific row.

    Args:
        tableName (str): Name of the table/resource to lock.
        pk (Optional[int]): Optional primary key for row-level locking.
        timeOut (int): Lock expiration in seconds (auto-released after this).
        blockingTimeOut (int): Maximum time (in seconds) to wait for lock acquisition.

    Returns:
        Lock: A Redis lock object if successfully acquired.

    Raises:
        exceptions.LockAcquireTimeout: If the lock could not be acquired within blockingTimeOut.
    """
    try:
        lockName = f"lock:{tableName}" if pk is None else f"lock:{tableName}:{pk}"
        lock = redisClient.lock(lockName, timeout=timeOut)
        if lock.acquire(blocking=True, blocking_timeout=blockingTimeOut):
            return lock
        raise exceptions.LockAcquireTimeout()
    except Exception as e:
        exceptions.handle(e)


def releaseLock(lock: Optional[Lock]) -> None:
    """
    Release a previously acquired Redis lock.

    Args:
        lock (Lock | None): The Redis lock object to release. Does nothing if None.

    Notes:
        - Ensures only the owner can release the lock.
        - Silently ignores invalid/unowned locks.
    """
    if lock and lock.locked() and lock.owned():
        lock.release()
