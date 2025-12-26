from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List
from uuid import UUID

import httpx
from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.core.areas.models import Area
from app.core.auth.models import User
from app.core.config import settings
from app.core.future_story.schemas import FutureStoryAIResponse, FutureStoryPublic
from app.core.future_story.services import (
    create_future_story,
    get_latest_draft,
    mark_draft_completed,
)
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
    path = settings.future_story_system_prompt_path
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _fetch_active_areas(db: Session) -> Dict[str, str]:
    rows = (
        db.query(Area)
        .filter(Area.is_active.is_(True))
        .order_by(asc(Area.order_index), asc(Area.id))
        .all()
    )
    return {row.id: row.title for row in rows}


def _group_answers(
    answers: List[Dict[str, Any]],
    area_titles: Dict[str, str],
) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for item in answers:
        area_id = item.get("area_id")
        question = item.get("question")
        answer = item.get("answer")
        if not area_id or not question or not answer:
            continue

        if area_id not in grouped:
            grouped[area_id] = {
                "area_id": area_id,
                "area_title": area_titles.get(area_id, area_id),
                "qa": [],
            }
        grouped[area_id]["qa"].append(
            {
                "question": question,
                "answer": answer,
            }
        )
    return list(grouped.values())


def _call_ai_proxy(system_prompt: str, payload: Dict[str, Any]) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]

    request_body = {
        "model": settings.ai_proxy_model,
        "messages": messages,
        "temperature": 0.3,
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


@celery_app.task(name="future_story.generate")
def generate_future_story_task(user_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        try:
            user_uuid = UUID(user_id)
        except ValueError:
            return _error("FUTURE_STORY_INVALID_USER_ID", "Invalid user_id.", 400)

        user = db.query(User).filter(User.id == user_uuid).first()
        if user is None:
            return _error("FUTURE_STORY_USER_NOT_FOUND", "User not found.", 404)

        draft = get_latest_draft(db, user_uuid)
        if draft is None or not draft.answers:
            return _error(
                "FUTURE_STORY_DRAFT_NOT_FOUND",
                "No draft answers found.",
                422,
            )

        area_titles = _fetch_active_areas(db)
        answers_by_area = _group_answers(draft.answers or [], area_titles)
        if not answers_by_area:
            return _error(
                "FUTURE_STORY_EMPTY_ANSWERS",
                "Draft answers are empty.",
                422,
            )

        wants_analysis = get_latest_analysis(db, user_uuid)
        app_state = {}
        main_pains: List[str] = []
        if wants_analysis is not None:
            app_state = {
                "wants_analysis": {
                    "top_wants": wants_analysis.top_wants,
                    "top_pains": wants_analysis.top_pains,
                }
            }
            for pain in wants_analysis.top_pains or []:
                area_id = pain.get("area_id")
                if area_id and area_id not in main_pains:
                    main_pains.append(area_id)

        payload = {
            "mode": "build_future_story",
            "user_profile": {
                "age": _calc_age(user.date_of_birth),
                "gender": user.gender,
                "main_pains": main_pains,
            },
            "app_state": app_state,
            "payload": {
                "use_existing_draft": False,
                "answers_by_area": answers_by_area,
            },
        }

        system_prompt = _load_system_prompt()
        ai_content = _call_ai_proxy(system_prompt, payload)

        parsed = json.loads(ai_content)
        ai_response = FutureStoryAIResponse.model_validate(parsed).model_dump()

        story = create_future_story(
            db=db,
            user_id=user_uuid,
            horizon_3y=ai_response["future_story_3y"],
            horizon_5y=ai_response["future_story_5y"],
            key_images=ai_response["key_images"],
            validation_notes=ai_response.get("validation_notes"),
        )
        mark_draft_completed(db, draft)

        story_public = FutureStoryPublic.model_validate(story).model_dump(mode="json")
        return {"ok": True, "story": story_public}
    except FileNotFoundError as exc:
        return _error("FUTURE_STORY_PROMPT_NOT_FOUND", str(exc), 500)
    except httpx.HTTPError as exc:
        return _error("FUTURE_STORY_AI_PROXY_ERROR", str(exc), 502)
    except (json.JSONDecodeError, ValueError) as exc:
        return _error("FUTURE_STORY_AI_PARSE_ERROR", str(exc), 502)
    except Exception as exc:
        return _error("FUTURE_STORY_UNEXPECTED_ERROR", str(exc), 500)
    finally:
        db.close()
