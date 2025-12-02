from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from passlib.context import CryptContext

from app.core.config import settings
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    expires_delta: Optional[timedelta] = None,
) -> str:
    now = _utc_now()
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "type": "access",
        "session_id": str(session_id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def create_refresh_token(
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    jti: Optional[uuid.UUID] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    now = _utc_now()
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(days=settings.refresh_token_expire_days)
    )
    jti_value = jti or uuid.uuid4()
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "type": "refresh",
        "session_id": str(session_id),
        "jti": str(jti_value),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


def generate_random_token() -> str:
    return secrets.token_urlsafe(32)


__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "generate_random_token",
]
