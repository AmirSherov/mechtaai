from __future__ import annotations

import smtplib
from email.message import EmailMessage

from loguru import logger

from app.core.config import settings
from app.core.auth.models import EmailVerificationToken
from app.database.session import SessionLocal
from mechtaai_bg_worker.celery_app import celery_app


def _send_email_sync(recipient: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email or settings.smtp_username
    msg["To"] = recipient
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
    except Exception as exc:
        logger.error(
            "Failed to send email",
            exc_info=exc,
        )
        raise


@celery_app.task(name="email.send_verification_email")
def send_verification_email(email: str, code: str, token: str) -> None:
    subject = "Подтверждение email"
    body = (
        f"Ваш код подтверждения: {code}\n\n"
        "Введите этот код в приложении, чтобы завершить регистрацию."
    )
    logger.info(
        "Sending verification email",
        extra={"email": email},
    )
    _send_email_sync(email, subject, body)


@celery_app.task(name="email.cleanup_verification_tokens")
def cleanup_verification_tokens() -> None:
    from app.core.auth.services import _utc_now

    logger.info("Running cleanup_verification_tokens task")
    db = SessionLocal()
    try:
        now = _utc_now()
        (
            db.query(EmailVerificationToken)
            .filter(EmailVerificationToken.expires_at <= now)
            .delete(synchronize_session=False)
        )
        db.commit()
    except Exception as exc:
        logger.error("Failed to cleanup email verification tokens", exc_info=exc)
        db.rollback()
        raise
    finally:
        db.close()


__all__ = ["send_verification_email", "cleanup_verification_tokens"]

