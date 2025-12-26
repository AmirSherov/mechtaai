from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.areas.models import Area
from app.core.auth.models import User
from app.core.config import settings
from app.core.future_story.services import get_latest_story
from app.core.generate_goals.schemas import GoalsAIResponse
from app.core.generate_goals.services import create_generation_log
from app.core.wants.services import get_latest_analysis
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
    path = settings.generate_goals_system_prompt_path
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _fetch_areas(db: Session) -> List[Dict[str, str]]:
    rows = db.query(Area).filter(Area.is_active.is_(True)).all()
    return [{"id": row.id, "title": row.title} for row in rows]


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


@celery_app.task(name="goals.generate")
def generate_goals_task(
    user_id: str,
    payload_override: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        try:
            user_uuid = UUID(user_id)
        except ValueError:
            return _error("GOALS_INVALID_USER_ID", "Invalid user_id.", 400)

        user = db.query(User).filter(User.id == user_uuid).first()
        if user is None:
            return _error("GOALS_USER_NOT_FOUND", "User not found.", 404)

        story = get_latest_story(db, user_uuid)
        if story is None:
            return _error(
                "GOALS_FUTURE_STORY_NOT_FOUND",
                "No future story found.",
                422,
            )

        wants_analysis = get_latest_analysis(db, user_uuid)
        diagnosis = {}
        main_pains: List[str] = []
        if wants_analysis is not None:
            diagnosis = {
                "top_wants": wants_analysis.top_wants,
                "top_pains": wants_analysis.top_pains,
                "focus_areas": wants_analysis.focus_areas,
            }
            for pain in wants_analysis.top_pains or []:
                area_id = pain.get("area_id")
                if area_id and area_id not in main_pains:
                    main_pains.append(area_id)

        limits = {"max_goals_1y": 5, "max_goals_3y": 5, "max_goals_5y": 5}
        if payload_override and payload_override.get("limits"):
            limits.update(payload_override["limits"])

        payload = {
            "mode": "generate_goals",
            "user_profile": {
                "age": _calc_age(user.date_of_birth),
                "life_format": user.life_format,
                "main_pains": main_pains,
            },
            "app_state": {
                "diagnosis": diagnosis,
                "areas": _fetch_areas(db),
            },
            "payload": {
                "future_story_3y": story.horizon_3y.get("full_text"),
                "future_story_5y": story.horizon_5y.get("full_text"),
                "limits": limits,
            },
        }

        system_prompt = _load_system_prompt()
        ai_content = _call_ai_proxy(system_prompt, payload)

        parsed = json.loads(ai_content)
        ai_response = GoalsAIResponse.model_validate(parsed).model_dump()

        def attach_horizon(items: List[Dict[str, Any]], horizon: str) -> List[Dict[str, Any]]:
            return [dict(item, horizon=horizon) for item in items]

        payload_out = {
            "goals_1y": attach_horizon(ai_response["goals_1y"], "1y"),
            "goals_3y": attach_horizon(ai_response["goals_3y"], "3y"),
            "goals_5y": attach_horizon(ai_response["goals_5y"], "5y"),
            "comment_for_user": ai_response["comment_for_user"],
            "suggested_to_drop": ai_response.get("suggested_to_drop", []),
        }

        create_generation_log(
            db=db,
            user_id=user_uuid,
            comment_for_user=ai_response.get("comment_for_user"),
            suggested_to_drop=ai_response.get("suggested_to_drop", []),
        )

        return {"ok": True, "payload": payload_out}
    except FileNotFoundError as exc:
        return _error("GOALS_PROMPT_NOT_FOUND", str(exc), 500)
    except httpx.HTTPError as exc:
        return _error("GOALS_AI_PROXY_ERROR", str(exc), 502)
    except (json.JSONDecodeError, ValueError) as exc:
        return _error("GOALS_AI_PARSE_ERROR", str(exc), 502)
    except Exception as exc:
        return _error("GOALS_AI_UNEXPECTED_ERROR", str(exc), 500)
    finally:
        db.close()
