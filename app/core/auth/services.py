from __future__ import annotations

import random
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.auth.models import (
    EmailVerificationToken,
    LoginAttempt,
    PasswordResetToken,
    User,
    UserSession,
)
from app.core.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RequestPasswordReset,
    ResetPasswordConfirm,
    TelegramAuthRequest,
    TokenPair,
    UserCreate,
)
from app.core.config import settings
from app.core.notifications.email import schedule_email_verification
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_random_token,
    hash_password,
    verify_password,
)
from app.response.response import APIError


PASSWORD_MIN_LENGTH = 8
MAX_VERIFICATION_ATTEMPTS = 5


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_password_strength(password: str) -> None:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise APIError(
            code="AUTH_PASSWORD_TOO_SHORT",
            http_code=400,
            message=f"Пароль должен содержать не менее {PASSWORD_MIN_LENGTH} символов",
        )

    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)

    if not (has_lower and has_upper and has_digit and has_special):
        raise APIError(
            code="AUTH_PASSWORD_TOO_WEAK",
            http_code=400,
            message=(
                "Пароль должен содержать строчные и заглавные буквы, "
                "цифры и хотя бы один специальный символ"
            ),
        )


def _generate_strong_password(length: int = 20) -> str:
    if length < 12:
        length = 12
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%^&*()-_=+"
    all_chars = lower + upper + digits + special

    password_chars = [
        secrets.choice(lower),
        secrets.choice(upper),
        secrets.choice(digits),
        secrets.choice(special),
    ]
    password_chars.extend(
        secrets.choice(all_chars) for _ in range(length - len(password_chars))
    )
    secrets.SystemRandom().shuffle(password_chars)
    return "".join(password_chars)


def create_user(
    db: Session,
    data: UserCreate,
) -> User:
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise APIError(
            code="AUTH_EMAIL_ALREADY_EXISTS",
            http_code=400,
            message="Пользователь с таким email уже существует",
        )

    validate_password_strength(data.password)

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        time_zone=data.time_zone or "Europe/Moscow",
        date_of_birth=data.date_of_birth,
        gender=data.gender,
        life_format=data.life_format,
        locale=data.locale or "ru-RU",
        is_active=False,
    )
    db.add(user)
    db.flush()
    db.refresh(user)

    from app.core.gamification.models import GamificationProfile

    profile = GamificationProfile(
        user_id=user.id,
        total_xp=0,
        current_level=1,
        current_streak=0,
        longest_streak=0,
        last_activity_date=None,
    )
    db.add(profile)
    return user


def authenticate_user(
    db: Session,
    data: LoginRequest,
) -> User:
    user = db.query(User).filter(User.email == data.email).first()
    if user is None:
        raise APIError(
            code="AUTH_INVALID_CREDENTIALS",
            http_code=401,
            message="Неверный email или пароль",
        )

    if not verify_password(data.password, user.password_hash):
        raise APIError(
            code="AUTH_INVALID_CREDENTIALS",
            http_code=401,
            message="Неверный email или пароль",
        )

    if not user.is_active:
        raise APIError(
            code="AUTH_USER_INACTIVE",
            http_code=403,
            message="Пользователь деактивирован или email не подтвержден",
        )

    return user


def authenticate_telegram_user(
    db: Session,
    data: TelegramAuthRequest,
) -> User:
    user = (
        db.query(User)
        .filter(User.telegram_id == data.telegram_id)
        .first()
    )
    if user is not None:
        if not user.is_active:
            raise APIError(
                code="AUTH_USER_INACTIVE",
                http_code=403,
                message="User is inactive",
            )
        updated = False
        if data.first_name and data.first_name != user.first_name:
            user.first_name = data.first_name
            updated = True
        if data.last_name and data.last_name != user.last_name:
            user.last_name = data.last_name
            updated = True
        if updated:
            db.add(user)
        return user

    if data.first_name is None:
        raise APIError(
            code="AUTH_TELEGRAM_USER_NOT_FOUND",
            http_code=404,
            message="User not found. Registration required.",
        )

    email = f"{data.telegram_id}@bot.mechta.ai"
    password = _generate_strong_password()
    payload = UserCreate(
        email=email,
        password=password,
        first_name=data.first_name,
        last_name=data.last_name,
    )
    user = create_user(db, payload)
    user.is_active = True
    user.telegram_id = data.telegram_id
    db.add(user)
    return user


def _create_session(
    db: Session,
    user: User,
    *,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
    device_name: Optional[str] = None,
) -> Tuple[UserSession, uuid.UUID]:
    now = _utc_now()
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    refresh_id = uuid.uuid4()
    session = UserSession(
        user_id=user.id,
        refresh_token_id=str(refresh_id),
        user_agent=user_agent,
        ip_address=ip_address,
        device_name=device_name,
        expires_at=expires_at,
    )
    db.add(session)
    db.flush()
    db.refresh(session)
    return session, refresh_id


def create_session_and_tokens(
    db: Session,
    user: User,
    *,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
    device_name: Optional[str] = None,
) -> TokenPair:
    session, refresh_id = _create_session(
        db,
        user,
        user_agent=user_agent,
        ip_address=ip_address,
        device_name=device_name,
    )

    access_token = create_access_token(
        user_id=user.id,
        session_id=session.id,
    )
    refresh_token = create_refresh_token(
        user_id=user.id,
        session_id=session.id,
        jti=refresh_id,
    )
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
    )


def refresh_tokens(
    db: Session,
    refresh_token: str,
) -> TokenPair:
    from app.core.security import decode_token

    try:
        payload = decode_token(refresh_token)
    except Exception:
        raise APIError(
            code="AUTH_INVALID_REFRESH_TOKEN",
            http_code=401,
            message="Невалидный или просроченный refresh-токен",
        )

    if payload.get("type") != "refresh":
        raise APIError(
            code="AUTH_INVALID_TOKEN_TYPE",
            http_code=401,
            message="Неверный тип токена",
        )

    user_id_str = payload.get("sub")
    session_id_str = payload.get("session_id")
    jti_str = payload.get("jti")

    try:
        user_id = uuid.UUID(user_id_str)
        session_id = uuid.UUID(session_id_str)
    except Exception:
        raise APIError(
            code="AUTH_INVALID_TOKEN_PAYLOAD",
            http_code=401,
            message="Некорректный payload токена",
        )

    session = (
        db.query(UserSession)
        .filter(UserSession.id == session_id)
        .first()
    )
    if session is None:
        raise APIError(
            code="AUTH_SESSION_NOT_FOUND",
            http_code=401,
            message="Сессия не найдена",
        )

    now = _utc_now()
    if session.revoked_at is not None or session.expires_at <= now:
        raise APIError(
            code="AUTH_SESSION_REVOKED",
            http_code=401,
            message="Сессия завершена",
        )

    if session.refresh_token_id != jti_str:
        raise APIError(
            code="AUTH_REFRESH_JTI_MISMATCH",
            http_code=401,
            message="Refresh-токен не соответствует сессии",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise APIError(
            code="AUTH_USER_NOT_FOUND",
            http_code=401,
            message="Пользователь не найден",
        )

    if not user.is_active:
        raise APIError(
            code="AUTH_USER_INACTIVE",
            http_code=403,
            message="Пользователь деактивирован или email не подтвержден",
        )

    access_token = create_access_token(
        user_id=user.id,
        session_id=session.id,
    )
    new_refresh_token = create_refresh_token(
        user_id=user.id,
        session_id=session.id,
        jti=uuid.UUID(jti_str),
    )

    return TokenPair(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


def _generate_verification_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def create_email_verification_token(
    db: Session,
    user: User,
) -> EmailVerificationToken:
    now = _utc_now()
    expires_at = now + timedelta(
        hours=settings.email_verification_token_expire_hours
    )
    token_str = generate_random_token()
    code = _generate_verification_code()

    token = EmailVerificationToken(
        user_id=user.id,
        email=user.email,
        token=token_str,
        code=code,
        expires_at=expires_at,
    )
    db.add(token)
    db.flush()
    db.refresh(token)
    return token


def send_email_verification(
    db: Session,
    email: str,
) -> str:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise APIError(
            code="AUTH_USER_NOT_FOUND",
            http_code=404,
            message="Пользователь с таким email не найден",
        )

    if user.is_active:
        raise APIError(
            code="AUTH_EMAIL_ALREADY_VERIFIED",
            http_code=400,
            message="Email уже подтвержден",
        )

    (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        )
        .update({"used_at": _utc_now()})
    )

    token = create_email_verification_token(db, user)

    schedule_email_verification(
        email=user.email,
        code=token.code,
        token=token.token,
    )

    return token.token


def logout_session(
    db: Session,
    *,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    session = (
        db.query(UserSession)
        .filter(UserSession.id == session_id, UserSession.user_id == user_id)
        .first()
    )
    if session is None:
        raise APIError(
            code="AUTH_SESSION_NOT_FOUND",
            http_code=404,
            message="Сессия не найдена",
        )

    now = _utc_now()
    session.revoked_at = now
    db.add(session)


def logout_all_sessions(
    db: Session,
    *,
    user_id: uuid.UUID,
) -> None:
    now = _utc_now()
    (
        db.query(UserSession)
        .filter(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .update({"revoked_at": now})
    )


def request_password_reset(
    db: Session,
    data: RequestPasswordReset,
) -> None:
    user = db.query(User).filter(User.email == data.email).first()
    if user is None:
        return

    token_str = generate_random_token()
    expires_at = _utc_now() + timedelta(
        minutes=settings.password_reset_token_expire_minutes
    )
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token_str,
        expires_at=expires_at,
    )
    db.add(reset_token)


def reset_password(
    db: Session,
    data: ResetPasswordConfirm,
) -> None:
    reset = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token == data.token)
        .first()
    )
    if reset is None:
        raise APIError(
            code="AUTH_RESET_TOKEN_NOT_FOUND",
            http_code=400,
            message="Некорректный или уже использованный токен сброса",
        )

    now = _utc_now()
    if reset.used_at is not None or reset.expires_at <= now:
        raise APIError(
            code="AUTH_RESET_TOKEN_EXPIRED",
            http_code=400,
            message="Токен сброса пароля просрочен или уже использован",
        )

    user = db.query(User).filter(User.id == reset.user_id).first()
    if user is None:
        raise APIError(
            code="AUTH_USER_NOT_FOUND",
            http_code=400,
            message="Пользователь не найден",
        )

    validate_password_strength(data.new_password)

    user.password_hash = hash_password(data.new_password)
    reset.used_at = now

    db.add(user)
    db.add(reset)

    logout_all_sessions(db, user_id=user.id)


QR_LOGIN_TOKEN_TTL_SECONDS = 180
QR_LOGIN_MAX_ATTEMPTS_PER_IP = 5
QR_LOGIN_RATE_LIMIT_WINDOW_MINUTES = 5


def _generate_login_token() -> str:
    return f"login_{secrets.token_urlsafe(32)}"


def _generate_one_time_secret() -> str:
    return secrets.token_urlsafe(48)


def create_qr_login_attempt(
    db: Session,
    *,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[str, str, str, int]:
    from app.core.auth.models import LoginAttempt
    
    if ip_address:
        now = _utc_now()
        recent_window = now - timedelta(minutes=QR_LOGIN_RATE_LIMIT_WINDOW_MINUTES)
        recent_attempts_count = (
            db.query(LoginAttempt)
            .filter(
                LoginAttempt.ip_address == ip_address,
                LoginAttempt.created_at >= recent_window,
            )
            .count()
        )
        
        if recent_attempts_count >= QR_LOGIN_MAX_ATTEMPTS_PER_IP:
            raise APIError(
                code="AUTH_QR_RATE_LIMIT",
                http_code=429,
                message="Слишком много попыток входа. Попробуйте позже.",
            )
    
    login_token = _generate_login_token()
    now = _utc_now()
    expires_at = now + timedelta(seconds=QR_LOGIN_TOKEN_TTL_SECONDS)
    
    deep_link = f"https://t.me/mechtaai_official_bot?start={login_token}"
    qr_code_data = deep_link
    
    attempt = LoginAttempt(
        token=login_token,
        status="pending",
        ip_address=ip_address,
        user_agent=user_agent,
        qr_code_data=qr_code_data,
        expires_at=expires_at,
    )
    db.add(attempt)
    db.flush()
    
    return login_token, qr_code_data, deep_link, QR_LOGIN_TOKEN_TTL_SECONDS


def get_qr_login_status(
    db: Session,
    login_token: str,
) -> tuple[str, str | None]:
    from app.core.auth.models import LoginAttempt
    
    attempt = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.token == login_token)
        .first()
    )
    
    if not attempt:
        raise APIError(
            code="AUTH_QR_TOKEN_NOT_FOUND",
            http_code=404,
            message="Токен авторизации не найден",
        )
    
    now = _utc_now()
    if attempt.expires_at <= now:
        attempt.status = "expired"
        db.add(attempt)
        raise APIError(
            code="AUTH_QR_TOKEN_EXPIRED",
            http_code=400,
            message="Токен авторизации истек. Создайте новый QR-код.",
        )
    
    if attempt.status == "confirmed":
        if not attempt.one_time_secret:
            raise APIError(
                code="AUTH_QR_SECRET_MISSING",
                http_code=500,
                message="Внутренняя ошибка при генерации секрета",
            )
        return "confirmed", attempt.one_time_secret
    
    return attempt.status, None


def confirm_qr_login(
    db: Session,
    *,
    login_token: str,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
    photo_url: str | None,
) -> None:
    from app.core.auth.models import LoginAttempt
    
    attempt = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.token == login_token)
        .with_for_update()
        .first()
    )
    
    if not attempt:
        raise APIError(
            code="AUTH_QR_TOKEN_NOT_FOUND",
            http_code=404,
            message="Токен авторизации не найден",
        )
    
    now = _utc_now()
    if attempt.expires_at <= now:
        attempt.status = "expired"
        db.add(attempt)
        raise APIError(
            code="AUTH_QR_TOKEN_EXPIRED",
            http_code=400,
            message="Токен авторизации истек",
        )
    
    if attempt.status != "pending":
        raise APIError(
            code="AUTH_QR_ALREADY_USED",
            http_code=400,
            message="Этот токен уже был использован",
        )
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    
    if not user:
        if not first_name:
            raise APIError(
                code="AUTH_TELEGRAM_FIRST_NAME_REQUIRED",
                http_code=400,
                message="Имя пользователя обязательно для регистрации",
            )
        
        email = f"{telegram_id}@bot.mechta.ai"
        password = _generate_strong_password()
        payload = UserCreate(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        user = create_user(db, payload)
        user.is_active = True
        user.telegram_id = telegram_id
        db.add(user)
        db.flush()
    else:
        updated = False
        if first_name and first_name != user.first_name:
            user.first_name = first_name
            updated = True
        if last_name and last_name != user.last_name:
            user.last_name = last_name
            updated = True
        if updated:
            db.add(user)
    
    one_time_secret = _generate_one_time_secret()
    
    attempt.status = "confirmed"
    attempt.user_id = user.id
    attempt.telegram_id = telegram_id
    attempt.telegram_username = username
    attempt.telegram_first_name = first_name
    attempt.telegram_last_name = last_name
    attempt.telegram_photo_url = photo_url
    attempt.one_time_secret = one_time_secret
    attempt.confirmed_at = now
    
    db.add(attempt)


def exchange_qr_secret_for_tokens(
    db: Session,
    one_time_secret: str,
    *,
    user_agent: str | None = None,
) -> tuple[User, TokenPair]:
    from app.core.auth.models import LoginAttempt
    
    attempt = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.one_time_secret == one_time_secret)
        .with_for_update()
        .first()
    )
    
    if not attempt:
        raise APIError(
            code="AUTH_QR_SECRET_INVALID",
            http_code=401,
            message="Неверный секретный ключ",
        )
    
    if attempt.status != "confirmed":
        raise APIError(
            code="AUTH_QR_NOT_CONFIRMED",
            http_code=400,
            message="Попытка входа еще не подтверждена",
        )
    
    if attempt.used_at is not None:
        raise APIError(
            code="AUTH_QR_ALREADY_EXCHANGED",
            http_code=400,
            message="Этот секрет уже был использован",
        )
    
    now = _utc_now()
    if attempt.expires_at <= now:
        raise APIError(
            code="AUTH_QR_TOKEN_EXPIRED",
            http_code=400,
            message="Время действия токена истекло",
        )
    
    if not attempt.user_id:
        raise APIError(
            code="AUTH_QR_USER_NOT_SET",
            http_code=500,
            message="Внутренняя ошибка: пользователь не найден",
        )
    
    user = db.query(User).filter(User.id == attempt.user_id).first()
    if not user:
        raise APIError(
            code="AUTH_USER_NOT_FOUND",
            http_code=404,
            message="Пользователь не найден",
        )
    
    if not user.is_active:
        raise APIError(
            code="AUTH_USER_INACTIVE",
            http_code=403,
            message="Пользователь деактивирован",
        )
    
    tokens = create_session_and_tokens(
        db,
        user,
        user_agent=user_agent or attempt.user_agent,
        ip_address=attempt.ip_address,
    )
    
    attempt.used_at = now
    db.add(attempt)
    
    return user, tokens


def cleanup_expired_qr_login_attempts(db: Session) -> int:
    from app.core.auth.models import LoginAttempt
    
    cutoff_time = _utc_now() - timedelta(seconds=QR_LOGIN_TOKEN_TTL_SECONDS * 2)
    
    count = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.created_at < cutoff_time)
        .delete(synchronize_session=False)
    )
    
    db.commit()
    return count


__all__ = [
    "create_user",
    "authenticate_user",
    "authenticate_telegram_user",
    "create_session_and_tokens",
    "refresh_tokens",
    "create_email_verification_token",
    "send_email_verification",
    "logout_session",
    "logout_all_sessions",
    "request_password_reset",
    "reset_password",
    "validate_password_strength",
    "create_qr_login_attempt",
    "get_qr_login_status",
    "confirm_qr_login",
    "exchange_qr_secret_for_tokens",
    "cleanup_expired_qr_login_attempts",
]
