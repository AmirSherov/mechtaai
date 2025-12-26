from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.future_story.models import FutureStory
from app.core.visuals.models import VisualAsset
from app.response.response import APIError


def _find_prompt_in_story(story: FutureStory, image_key: str) -> Tuple[str, str]:
    for horizon in (story.horizon_5y, story.horizon_3y):
        key_images = (horizon or {}).get("key_images") or []
        for item in key_images:
            if item.get("id") == image_key:
                text_ru = item.get("text_ru") or item.get("text") or ""
                prompt = item.get("dall_e_prompt")
                if not prompt:
                    raise APIError(
                        code="VISUALS_PROMPT_MISSING",
                        http_code=400,
                        message="dall_e_prompt не найден для image_key.",
                    )
                return text_ru, prompt

    legacy_key_images = story.key_images or []
    for item in legacy_key_images:
        if item.get("id") == image_key:
            text_ru = item.get("text_ru") or item.get("text") or ""
            prompt = item.get("dall_e_prompt")
            if not prompt:
                raise APIError(
                    code="VISUALS_PROMPT_MISSING",
                    http_code=400,
                    message="dall_e_prompt не найден для image_key.",
                )
            return text_ru, prompt
    raise APIError(
        code="VISUALS_IMAGE_KEY_NOT_FOUND",
        http_code=404,
        message="image_key не найден в future_story.",
    )


def _call_image_proxy(prompt: str) -> str:
    payload = {
        "prompt": prompt,
        "model": "dall-e-3",
        "n": 1,
        "size": "1024x1024",
        "quality": "standard",
        "response_format": "url",
    }
    with httpx.Client(timeout=settings.ai_proxy_timeout_seconds) as client:
        response = client.post(settings.ai_proxy_image_url, json=payload)
    response.raise_for_status()
    data = response.json()
    url = data.get("url")
    if not isinstance(url, str) or not url:
        raise APIError(
            code="VISUALS_AI_BAD_RESPONSE",
            http_code=502,
            message="AI image proxy вернул пустой url.",
        )
    return url


def _download_image(url: str) -> bytes:
    with httpx.Client(timeout=settings.ai_proxy_timeout_seconds) as client:
        response = client.get(url)
    response.raise_for_status()
    return response.content


def _save_image(
    user_id: UUID,
    image_key: str,
    content: bytes,
) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    rel_dir = Path("uploads") / str(user_id) / "future_story_generated_images"
    rel_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{image_key}_{timestamp}.png"
    path = rel_dir / filename
    path.write_bytes(content)
    return f"/uploads/{user_id}/future_story_generated_images/{filename}"


def generate_and_save(
    db: Session,
    user_id: UUID,
    story_id: UUID,
    image_key: str,
) -> VisualAsset:
    story = (
        db.query(FutureStory)
        .filter(FutureStory.id == story_id, FutureStory.user_id == user_id)
        .first()
    )
    if story is None:
        raise APIError(
            code="VISUALS_STORY_NOT_FOUND",
            http_code=404,
            message="Future story не найдена.",
        )

    _text_ru, prompt = _find_prompt_in_story(story, image_key)
    temp_url = _call_image_proxy(prompt)
    content = _download_image(temp_url)
    local_path = _save_image(user_id, image_key, content)

    asset = VisualAsset(
        user_id=user_id,
        entity_type="vision_board",
        entity_id=story_id,
        image_key=image_key,
        local_path=local_path,
        ai_prompt=prompt,
        provider="dall-e-3",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def list_story_assets(
    db: Session,
    user_id: UUID,
    story_id: UUID,
) -> list[VisualAsset]:
    return (
        db.query(VisualAsset)
        .filter(
            VisualAsset.user_id == user_id,
            VisualAsset.entity_id == story_id,
        )
        .order_by(VisualAsset.created_at.desc())
        .all()
    )


def regenerate_asset(
    db: Session,
    user_id: UUID,
    asset_id: UUID,
) -> VisualAsset:
    asset = (
        db.query(VisualAsset)
        .filter(VisualAsset.user_id == user_id, VisualAsset.id == asset_id)
        .first()
    )
    if asset is None:
        raise APIError(
            code="VISUALS_ASSET_NOT_FOUND",
            http_code=404,
            message="Visual asset не найден.",
        )

    temp_url = _call_image_proxy(asset.ai_prompt)
    content = _download_image(temp_url)
    local_path = _save_image(user_id, asset.image_key, content)
    asset.local_path = local_path
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


__all__ = [
    "generate_and_save",
    "list_story_assets",
    "regenerate_asset",
]
