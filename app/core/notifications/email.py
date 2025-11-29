from __future__ import annotations

from loguru import logger

from mechtaai_bg_worker.email_worker import send_verification_email


def schedule_email_verification(
    *,
    email: str,
    code: str,
    token: str,
) -> None:
    """
    Планировщик задач для отправки писем подтверждения email.

    Вызывает Celery-задачу `send_verification_email` в отдельном воркере.
    """
    logger.info(
        "Scheduling verification email via Celery",
        email=email,
    )
    send_verification_email.delay(email=email, code=code, token=token)


__all__ = ["schedule_email_verification"]
