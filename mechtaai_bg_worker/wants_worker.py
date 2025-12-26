from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict
from uuid import UUID

import httpx
from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.areas.models import Area
from app.core.config import settings
from app.core.wants.schemas import WantsAnalysisPayload, WantsAnalysisPublic
from app.core.wants.services import create_wants_analysis, get_latest_completed
from app.database.session import SessionLocal
from mechtaai_bg_worker.celery_app import celery_app


def _calc_age(birth_date: date | None) -> int | None:
    if birth_date is None:
        return None
    today = date.today()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return max(age, 0)


def _load_system_prompt() -> str:
    path = settings.wants_ai_system_prompt_path
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _fetch_active_areas(db: Session) -> list[dict[str, Any]]:
    rows = (
        db.query(Area)
        .filter(Area.is_active.is_(True))
        .order_by(asc(Area.order_index), asc(Area.id))
        .all()
    )
    return [
        {
            "id": row.id,
            "title": row.title,
        }
        for row in rows
    ]


def _build_payload(user: User, wants_raw) -> Dict[str, Any]:
    return {
        "mode": "diagnose_wants",
        "user_profile": {
            "age": _calc_age(user.date_of_birth),
            "gender": user.gender,
            "life_format": user.life_format,
        },
        "payload": {
            "raw_wants_stream": wants_raw.raw_wants_stream,
            "raw_future_me": wants_raw.raw_future_me,
            "raw_envy": wants_raw.raw_envy,
            "raw_regrets": wants_raw.raw_regrets,
            "raw_what_to_do_5y": wants_raw.raw_what_to_do_5y,
        },
    }


def _call_ai_proxy(system_prompt: str, payload: Dict[str, Any]) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]

    request_body = {
        "model": settings.ai_proxy_model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    with httpx.Client(timeout=settings.ai_proxy_timeout_seconds) as client:
        response = client.post(settings.ai_proxy_url, json=request_body)
    response.raise_for_status()

    data = response.json()
    content = data.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("AI proxy returned empty content")
    return content


def _error(code: str, message: str, http_code: int = 400) -> Dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "http_code": http_code,
        },
    }


@celery_app.task(name="wants.analyze")
def analyze_wants_task(user_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        try:
            user_uuid = UUID(user_id)
        except ValueError:
            return _error("WANTS_INVALID_USER_ID", "Invalid user_id.", 400)

        user = db.query(User).filter(User.id == user_uuid).first()
        if user is None:
            return _error("WANTS_USER_NOT_FOUND", "User not found.", 404)

        wants_raw = get_latest_completed(db, user_uuid)
        if wants_raw is None:
            return _error(
                "WANTS_RAW_NOT_READY",
                "No completed wants_raw found.",
                422,
            )

        missing = []
        if not (wants_raw.raw_wants_stream or "").strip():
            missing.append("raw_wants_stream")
        if not (wants_raw.raw_future_me or "").strip():
            missing.append("raw_future_me")
        if not (wants_raw.raw_envy or "").strip():
            missing.append("raw_envy")
        if not (wants_raw.raw_regrets or "").strip():
            missing.append("raw_regrets")
        if not (wants_raw.raw_what_to_do_5y or "").strip():
            missing.append("raw_what_to_do_5y")
        if missing:
            return _error(
                "WANTS_RAW_NOT_READY",
                "Missing wants_raw fields.",
                422,
            )

        areas = _fetch_active_areas(db)
        payload = _build_payload(user, wants_raw)
        payload["payload"]["areas"] = areas

        system_prompt = _load_system_prompt()
        ai_content = _call_ai_proxy(system_prompt, payload)

        parsed = json.loads(ai_content)
        analysis_payload = WantsAnalysisPayload.model_validate(parsed).model_dump()
        analysis = create_wants_analysis(db, user_uuid, analysis_payload)
        analysis_public = (
            WantsAnalysisPublic.model_validate(analysis).model_dump(mode="json")
        )

        return {
            "ok": True,
            "analysis": analysis_public,
        }
    except FileNotFoundError as exc:
        return _error("WANTS_AI_PROMPT_NOT_FOUND", str(exc), 500)
    except httpx.HTTPError as exc:
        return _error("WANTS_AI_PROXY_ERROR", str(exc), 502)
    except (json.JSONDecodeError, ValueError) as exc:
        return _error("WANTS_AI_PARSE_ERROR", str(exc), 502)
    except Exception as exc:
        return _error("WANTS_AI_UNEXPECTED_ERROR", str(exc), 500)
    finally:
        db.close()
