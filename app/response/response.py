from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional


class APIError(Exception):
    def __init__(
        self,
        code: str,
        http_code: int,
        message: str,
        *,
        details: Optional[Any] = None,
        fields: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_code = http_code
        self.message = message
        self.details = details
        self.fields = fields

from pydantic import BaseModel, Field


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class Meta(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    pagination: Optional[Pagination] = None


class ErrorPayload(BaseModel):
    code: str
    http_code: int
    message: str
    details: Optional[Any] = None
    fields: Optional[Any] = None


class StandardResponse(BaseModel):
    ok: bool
    result: Optional[Any] = None
    error: Optional[ErrorPayload] = None
    meta: Meta = Field(default_factory=Meta)


def make_success_response(
    result: Any,
    *,
    pagination: Optional[Pagination] = None,
    request_id: Optional[str] = None,
) -> StandardResponse:
    meta = Meta(
        request_id=request_id or str(uuid.uuid4()),
        pagination=pagination,
    )
    return StandardResponse(
        ok=True,
        result=result,
        error=None,
        meta=meta,
    )


def make_error_response(
    code: str,
    http_code: int,
    message: str,
    *,
    details: Optional[Any] = None,
    fields: Optional[Any] = None,
    request_id: Optional[str] = None,
) -> StandardResponse:
    error = ErrorPayload(
        code=code,
        http_code=http_code,
        message=message,
        details=details,
        fields=fields,
    )
    meta = Meta(request_id=request_id or str(uuid.uuid4()))
    return StandardResponse(
        ok=False,
        result=None,
        error=error,
        meta=meta,
    )


__all__ = [
    "APIError",
    "Pagination",
    "Meta",
    "ErrorPayload",
    "StandardResponse",
    "make_success_response",
    "make_error_response",
]
