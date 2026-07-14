from __future__ import annotations

from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings


QUEUE_KEY_PREFIX = "processing-jobs"


@lru_cache
def get_redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def queue_key(queue_name: str) -> str:
    return f"{QUEUE_KEY_PREFIX}:{queue_name}"


def enqueue_job(queue_name: str, job_id: str) -> bool:
    try:
        get_redis_client().rpush(queue_key(queue_name), job_id)
        return True
    except RedisError:
        return False


def dequeue_job(queue_names: list[str], timeout: int = 5) -> tuple[str, str] | None:
    try:
        result = get_redis_client().blpop([queue_key(name) for name in queue_names], timeout=timeout)
    except RedisError:
        return None
    if result is None:
        return None
    queue_key_name, job_id = result
    return queue_key_name.replace(f"{QUEUE_KEY_PREFIX}:", "", 1), job_id


def is_queue_available() -> bool:
    try:
        return bool(get_redis_client().ping())
    except RedisError:
        return False
