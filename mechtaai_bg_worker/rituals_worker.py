from __future__ import annotations

import json
from typing import Any, Dict

import httpx

from app.core.config import settings
from app.core.rituals.schemas import WeeklyReviewAIResponse
from mechtaai_bg_worker.celery_app import celery_app


def _load_system_prompt() -> str:
    path = settings.weekly_review_system_prompt_path
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


@celery_app.task(name="rituals.weekly_review")
def weekly_review_task(
    user_id: str,
    payload_in: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        payload = {
            "mode": "weekly_review",
            "user_profile": {"name": payload_in.get("user_name") or "User"},
            "payload": {
                "week_dates": payload_in.get("week_dates"),
                "completed_steps": payload_in.get("completed_steps") or [],
                "failed_steps": payload_in.get("failed_steps") or [],
                "mood_avg": payload_in.get("mood_avg"),
                "user_reflection": payload_in.get("user_reflection"),
            },
        }

        system_prompt = _load_system_prompt()
        ai_content = _call_ai_proxy(system_prompt, payload)
        parsed = json.loads(ai_content)
        ai_response = WeeklyReviewAIResponse.model_validate(parsed).model_dump()
        return {"ok": True, "analysis": ai_response}
    except FileNotFoundError as exc:
        return _error("RITUALS_PROMPT_NOT_FOUND", str(exc), 500)
    except httpx.HTTPError as exc:
        return _error("RITUALS_AI_PROXY_ERROR", str(exc), 502)
    except (json.JSONDecodeError, ValueError) as exc:
        return _error("RITUALS_AI_PARSE_ERROR", str(exc), 502)
    except Exception as exc:
        return _error("RITUALS_AI_UNEXPECTED_ERROR", str(exc), 500)
