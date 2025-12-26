from __future__ import annotations

import sys

from mechtaai_bg_worker.celery_app import celery_app
from mechtaai_bg_worker import email_worker  # noqa: F401  импорт для регистрации задач
from mechtaai_bg_worker import wants_worker  # noqa: F401  импорт для регистрации задач
from mechtaai_bg_worker import future_story_worker  # noqa: F401  импорт для регистрации задач
from mechtaai_bg_worker import generate_goals_worker  # noqa: F401  импорт для регистрации задач
from mechtaai_bg_worker import plan_steps_worker  # noqa: F401  импорт для регистрации задач
from mechtaai_bg_worker import rituals_worker  # noqa: F401  импорт для регистрации задач


def main() -> None:
    # На Windows Celery не поддерживает prefork нормально, поэтому используем solo-пул.
    argv = ["worker", "--loglevel=info", "-P", "solo"]
    celery_app.worker_main(argv)


if __name__ == "__main__":
    main()
