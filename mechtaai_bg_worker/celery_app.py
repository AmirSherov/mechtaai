from __future__ import annotations

import socket

from celery import Celery
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from mechtaai_bg_worker.config import settings


def _choose_broker_url() -> str:
    """
    Сначала пробуем broker из настроек (обычно redis://redis:6379/0),
    если не доступен (DNS/коннект), откатываемся на локальный Redis.
    """
    primary = settings.celery_broker_url

    try:
        client = Redis.from_url(primary)
        client.ping()
        return primary
    except (RedisConnectionError, socket.gaierror):
        pass

    fallback = "redis://localhost:6379/0"
    client = Redis.from_url(fallback)
    client.ping()
    return fallback


broker_url = _choose_broker_url()

celery_app = Celery(
    "mechtaai_bg_worker",
    broker=broker_url,
)

celery_app.autodiscover_tasks(
    packages=["mechtaai_bg_worker"],
)


__all__ = ["celery_app"]
