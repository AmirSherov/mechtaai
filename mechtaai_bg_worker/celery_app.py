from __future__ import annotations

from celery import Celery

from mechtaai_bg_worker.config import settings


celery_app = Celery(
    "mechtaai_bg_worker",
    broker=settings.celery_broker_url,
)

celery_app.autodiscover_tasks(
    packages=["mechtaai_bg_worker"],
)


__all__ = ["celery_app"]

