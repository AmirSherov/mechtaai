from __future__ import annotations

from datetime import date, timedelta
from enum import Enum
from typing import Dict, List
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.gamification.models import Achievement, GamificationProfile, UserAchievement
from app.response.response import APIError


class ActionType(str, Enum):
    DAILY_RITUAL_MORNING = "DAILY_RITUAL_MORNING"
    DAILY_RITUAL_EVENING = "DAILY_RITUAL_EVENING"
    WEEKLY_REVIEW_COMPLETE = "WEEKLY_REVIEW_COMPLETE"
    GOAL_CREATED = "GOAL_CREATED"
    GOAL_STEP_COMPLETED = "GOAL_STEP_COMPLETED"
    GOAL_ACHIEVED_SMALL = "GOAL_ACHIEVED_SMALL"
    GOAL_ACHIEVED_BIG = "GOAL_ACHIEVED_BIG"
    VISION_BOARD_CREATED = "VISION_BOARD_CREATED"


ACTION_XP: Dict[ActionType, int] = {
    ActionType.DAILY_RITUAL_MORNING: 15,
    ActionType.DAILY_RITUAL_EVENING: 15,
    ActionType.WEEKLY_REVIEW_COMPLETE: 50,
    ActionType.GOAL_CREATED: 10,
    ActionType.GOAL_STEP_COMPLETED: 20,
    ActionType.GOAL_ACHIEVED_SMALL: 100,
    ActionType.GOAL_ACHIEVED_BIG: 500,
    ActionType.VISION_BOARD_CREATED: 30,
}

ACTION_LABELS: Dict[ActionType, str] = {
    ActionType.DAILY_RITUAL_MORNING: "Утренний ритуал",
    ActionType.DAILY_RITUAL_EVENING: "Вечерний ритуал",
    ActionType.WEEKLY_REVIEW_COMPLETE: "Еженедельный обзор",
    ActionType.GOAL_CREATED: "Создание цели",
    ActionType.GOAL_STEP_COMPLETED: "Шаг цели выполнен",
    ActionType.GOAL_ACHIEVED_SMALL: "Квартальная цель достигнута",
    ActionType.GOAL_ACHIEVED_BIG: "Годовая цель достигнута",
    ActionType.VISION_BOARD_CREATED: "Визуализация мечты",
}

LEVELS = [
    (1, 0, 150, "Новичок"),
    (2, 151, 450, "Искатель"),
    (3, 451, 1000, "Стратег"),
    (4, 1001, 2000, "Архитектор"),
    (5, 2001, None, "Демиург"),
]


def _get_level_by_xp(total_xp: int) -> int:
    for level, min_xp, max_xp, _title in LEVELS:
        if total_xp < min_xp:
            continue
        if max_xp is None or total_xp <= max_xp:
            return level
    return LEVELS[-1][0]


def _get_level_title(level: int) -> str:
    for lvl, _min_xp, _max_xp, title in LEVELS:
        if lvl == level:
            return title
    return LEVELS[0][3]


def _get_level_bounds(level: int) -> tuple[int, int | None]:
    for lvl, min_xp, max_xp, _title in LEVELS:
        if lvl == level:
            return min_xp, max_xp
    return LEVELS[0][1], LEVELS[0][2]


def _get_xp_to_next_level(total_xp: int) -> int:
    current_level = _get_level_by_xp(total_xp)
    _min_xp, max_xp = _get_level_bounds(current_level)
    if max_xp is None:
        return 0
    return max_xp - total_xp


def _get_progress_percent(total_xp: int) -> int:
    current_level = _get_level_by_xp(total_xp)
    min_xp, max_xp = _get_level_bounds(current_level)
    if max_xp is None or max_xp == min_xp:
        return 100
    raw = (total_xp - min_xp) / (max_xp - min_xp) * 100
    percent = int(round(raw))
    return max(0, min(100, percent))


def ensure_profile(db: Session, user_id: UUID) -> GamificationProfile:
    profile = (
        db.query(GamificationProfile)
        .filter(GamificationProfile.user_id == user_id)
        .first()
    )
    if profile is not None:
        return profile

    profile = GamificationProfile(
        user_id=user_id,
        total_xp=0,
        current_level=1,
        current_streak=0,
        longest_streak=0,
        last_activity_date=None,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def award_action(
    db: Session,
    user_id: UUID,
    action_type: ActionType | str,
) -> Dict[str, object]:
    if isinstance(action_type, str):
        try:
            action_type = ActionType(action_type)
        except ValueError:
            action_type = None
    if action_type not in ACTION_XP:
        raise APIError(
            code="GAMIFICATION_UNKNOWN_ACTION",
            http_code=400,
            message="Unknown gamification action.",
        )

    profile = ensure_profile(db, user_id)
    xp_gained = ACTION_XP[action_type]
    profile.total_xp += xp_gained

    today = date.today()
    yesterday = today - timedelta(days=1)
    streak_changed = False

    if profile.last_activity_date is None:
        profile.current_streak = 1
        streak_changed = True
    elif profile.last_activity_date == today:
        streak_changed = False
    elif profile.last_activity_date == yesterday:
        profile.current_streak += 1
        streak_changed = True
    else:
        profile.current_streak = 1
        streak_changed = True

    if streak_changed:
        profile.longest_streak = max(
            profile.longest_streak,
            profile.current_streak,
        )

    profile.last_activity_date = today

    new_level = _get_level_by_xp(profile.total_xp)
    level_up = new_level > profile.current_level
    if level_up:
        profile.current_level = new_level

    db.add(profile)
    db.commit()
    db.refresh(profile)

    return {
        "xp_gained": xp_gained,
        "total_xp": profile.total_xp,
        "level_up": level_up,
        "new_level": profile.current_level,
        "streak_bonus": False,
    }


def get_profile_payload(db: Session, user_id: UUID) -> Dict[str, object]:
    profile = ensure_profile(db, user_id)
    return {
        "level": profile.current_level,
        "level_title": _get_level_title(profile.current_level),
        "xp": profile.total_xp,
        "xp_to_next_level": _get_xp_to_next_level(profile.total_xp),
        "streak": profile.current_streak,
        "longest_streak": profile.longest_streak,
    }


def merge_award_results(results: List[Dict[str, object]]) -> Dict[str, object]:
    if not results:
        return {
            "xp_gained": 0,
            "total_xp": 0,
            "level_up": False,
            "new_level": 1,
            "streak_bonus": False,
        }
    total_xp = results[-1].get("total_xp", 0)
    new_level = results[-1].get("new_level", 1)
    level_up = any(r.get("level_up") for r in results)
    xp_gained = sum(int(r.get("xp_gained", 0)) for r in results)
    return {
        "xp_gained": xp_gained,
        "total_xp": total_xp,
        "level_up": level_up,
        "new_level": new_level,
        "streak_bonus": False,
    }


def build_gamification_event(
    action_type: ActionType | str,
    award_result: Dict[str, object],
) -> Dict[str, object]:
    if isinstance(action_type, str):
        action_type = ActionType(action_type)

    total_xp = int(award_result.get("total_xp", 0))
    current_level = int(award_result.get("new_level", 1))
    status = "level_up" if award_result.get("level_up") else "xp_added"
    level_title = _get_level_title(current_level)
    progress_percent = _get_progress_percent(total_xp)
    xp_gained = int(award_result.get("xp_gained", 0))
    label = ACTION_LABELS.get(action_type, "Действие")

    if status == "level_up":
        message = f"НОВЫЙ УРОВЕНЬ: {level_title}!"
    else:
        message = f"+{xp_gained} XP {label}"

    return {
        "status": status,
        "xp_gained": xp_gained,
        "total_xp": total_xp,
        "level": {
            "current": current_level,
            "title": level_title,
            "progress_percent": progress_percent,
        },
        "message": message,
    }


def list_achievements_with_status(
    db: Session,
    user_id: UUID,
) -> List[Dict[str, object]]:
    achievements = db.query(Achievement).order_by(Achievement.id.asc()).all()
    obtained = (
        db.query(UserAchievement.achievement_id)
        .filter(UserAchievement.user_id == user_id)
        .all()
    )
    obtained_ids = {row.achievement_id for row in obtained}

    result = []
    for item in achievements:
        result.append(
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "xp_reward": item.xp_reward,
                "icon_url": item.icon_url,
                "is_obtained": item.id in obtained_ids,
            }
        )
    return result


def get_leaderboard(
    db: Session,
    limit: int = 20,
) -> List[Dict[str, object]]:
    rows = (
        db.query(GamificationProfile)
        .order_by(desc(GamificationProfile.total_xp))
        .limit(limit)
        .all()
    )
    return [
        {
            "user_id": row.user_id,
            "total_xp": row.total_xp,
            "level": row.current_level,
        }
        for row in rows
    ]


__all__ = [
    "ActionType",
    "ACTION_XP",
    "ACTION_LABELS",
    "award_action",
    "merge_award_results",
    "build_gamification_event",
    "ensure_profile",
    "get_profile_payload",
    "list_achievements_with_status",
    "get_leaderboard",
]
