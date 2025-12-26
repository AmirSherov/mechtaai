from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.generate_goals.models import Goal
from app.core.plan_steps.schemas import PlanStepsAIResponse
from app.database.session import SessionLocal
from mechtaai_bg_worker.celery_app import celery_app


def _load_system_prompt() -> str:
    path = settings.plan_steps_system_prompt_path
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


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


def _default_year_bounds() -> Dict[str, Any]:
    year = date.today().year + 1
    return {
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "quarters": [
            {"id": "Q1", "start": f"{year}-01-01", "end": f"{year}-03-31"},
            {"id": "Q2", "start": f"{year}-04-01", "end": f"{year}-06-30"},
            {"id": "Q3", "start": f"{year}-07-01", "end": f"{year}-09-30"},
            {"id": "Q4", "start": f"{year}-10-01", "end": f"{year}-12-31"},
        ],
    }


@celery_app.task(name="steps.generate")
def generate_steps_task(
    user_id: str,
    payload_in: Dict[str, Any],
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        try:
            user_uuid = UUID(user_id)
        except ValueError:
            return _error("STEPS_INVALID_USER_ID", "Invalid user_id.", 400)

        goal_ids = payload_in.get("goal_ids") or []
        if not goal_ids:
            return _error("STEPS_EMPTY_GOALS", "goal_ids is required.", 400)

        goals: List[Goal] = (
            db.query(Goal)
            .filter(Goal.user_id == user_uuid, Goal.id.in_(goal_ids))
            .all()
        )
        if not goals:
            return _error("STEPS_GOALS_NOT_FOUND", "Goals not found.", 404)

        goals_payload = [
            {
                "id": str(goal.id),
                "area_id": goal.area_id,
                "title": goal.title,
                "description": goal.description,
                "metric": goal.metric,
                "target_date": goal.target_date.isoformat()
                if goal.target_date
                else None,
            }
            for goal in goals
        ]

        payload = {
            "goals_1y": goals_payload,
            "current_load_hint": payload_in.get("current_load_hint")
            or {"max_focus_goals": 3, "max_weekly_actions": 10},
            "year_bounds": payload_in.get("year_bounds") or _default_year_bounds(),
        }

        system_prompt = _load_system_prompt()
        ai_content = _call_ai_proxy(system_prompt, payload)

        parsed = json.loads(ai_content)
        ai_response = PlanStepsAIResponse.model_validate(parsed).model_dump()
        return {"ok": True, "payload": ai_response}
    except FileNotFoundError as exc:
        return _error("STEPS_PROMPT_NOT_FOUND", str(exc), 500)
    except httpx.HTTPError as exc:
        return _error("STEPS_AI_PROXY_ERROR", str(exc), 502)
    except (json.JSONDecodeError, ValueError) as exc:
        return _error("STEPS_AI_PARSE_ERROR", str(exc), 502)
    except Exception as exc:
        return _error("STEPS_AI_UNEXPECTED_ERROR", str(exc), 500)
    finally:
        db.close()
