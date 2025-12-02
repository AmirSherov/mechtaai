from __future__ import annotations

import socket
from typing import Optional

from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.config import settings


_redis_client: Optional[Redis] = None


def _create_redis_client() -> Redis:
    """
    Пытается подключиться по CELERY_BROKER_URL,
    а при ошибке DNS/коннекта — падает обратно на localhost:6379.
    Так работает и в docker-compose (host=redis), и при запуске uvicorn с хоста.
    """
    primary_url = settings.celery_broker_url
    try:
        client = Redis.from_url(primary_url, decode_responses=True)
        client.ping()
        return client
    except (RedisConnectionError, socket.gaierror):
        pass
    fallback_url = "redis://localhost:6379/0"
    client = Redis.from_url(fallback_url, decode_responses=True)
    client.ping()
    return client


def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = _create_redis_client()
    return _redis_client


__all__ = ["get_redis"]
