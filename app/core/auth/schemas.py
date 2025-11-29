from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr
from pydantic.config import ConfigDict


class UserPublic(BaseModel):
    id: uuid.UUID
    email: EmailStr
    first_name: str | None
    last_name: str | None
    time_zone: str
    date_of_birth: date | None
    gender: Literal["male", "female", "other"] | None
    life_format: Literal["employee", "self_employed", "business", "searching"] | None
    locale: str
    personal_new_year_type: Literal["calendar", "birthday", "custom"]
    personal_new_year_date: date | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None
    time_zone: str | None = None
    date_of_birth: date | None = None
    gender: Literal["male", "female", "other"] | None = None
    life_format: Literal["employee", "self_employed", "business", "searching"] | None = None
    locale: str | None = None


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    time_zone: str | None = None
    date_of_birth: date | None = None
    gender: Literal["male", "female", "other"] | None = None
    life_format: Literal["employee", "self_employed", "business", "searching"] | None = None
    locale: str | None = None
    personal_new_year_type: Literal["calendar", "birthday", "custom"] | None = None
    personal_new_year_date: date | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class RequestPasswordReset(BaseModel):
    email: EmailStr


class ResetPasswordConfirm(BaseModel):
    token: str
    new_password: str


class SessionPublic(BaseModel):
    id: uuid.UUID
    user_agent: str | None
    ip_address: str | None
    device_name: str | None
    created_at: datetime
    expires_at: datetime
    is_current: bool
    revoked_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SendEmailVerificationRequest(BaseModel):
    email: EmailStr


class CheckEmailVerificationCodeRequest(BaseModel):
    verification_token: str
    code: str


__all__ = [
    "UserPublic",
    "UserCreate",
    "UserUpdate",
    "TokenPair",
    "LoginRequest",
    "RefreshRequest",
    "ChangePasswordRequest",
    "RequestPasswordReset",
    "ResetPasswordConfirm",
    "SessionPublic",
    "SendEmailVerificationRequest",
    "CheckEmailVerificationCodeRequest",
]
