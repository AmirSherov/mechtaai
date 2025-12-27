from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from celery.exceptions import TimeoutError as CeleryTimeoutError

from app.core.auth.models import User
from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.core.limits.dependencies import check_text_quota
from app.core.wants.schemas import (
    WantsAnalysisPublic,
    WantsFutureMePublic,
    WantsFutureMeSetIn,
    WantsProgressPublic,
    WantsRawPublic,
    WantsReversePublic,
    WantsReverseUpdateIn,
    WantsStreamAppendPublic,
    WantsStreamStartPublic,
    WantsTextIn,
)
from app.core.wants.services import (
    append_future_me_text,
    append_stream_text,
    complete_wants,
    finish_future_me,
    finish_stream,
    get_completed_by_id,
    get_draft,
    get_history_page,
    get_latest_analysis,
    get_or_create_draft,
    set_future_me,
    start_stream,
    update_reverse,
)
from mechtaai_bg_worker.celery_app import celery_app
from app.response import Pagination, StandardResponse, make_success_response
from app.response.response import APIError


router = APIRouter(prefix="/wants", tags=["wants"])


def _preview(text: str | None, *, max_chars: int = 500) -> str | None:
    if not text:
        return None
    s = text.strip()
    if len(s) <= max_chars:
        return s
    return s[-max_chars:]


@router.post(
    "/raw",
    response_model=StandardResponse,
    summary="Создать/получить draft wants_raw",
    description=(
        "Создаёт запись `wants_raw` со статусом `draft` для текущего пользователя, "
        "или возвращает уже существующую draft-запись.\n\n"
        "Зачем это нужно:\n"
        "- это 'контейнер' для трёх упражнений (stream / future_me / reverse)\n"
        "- все промежуточные ответы сохраняются в одну запись\n\n"
        "Важно:\n"
        "- у пользователя может быть только один draft (уникальность обеспечена в БД)\n"
        "- completed записи нельзя менять (в этом случае сервис вернёт 409)\n"
    ),
)
def create_or_get_draft_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Создать (или получить) текущий `draft` wants_raw.

    Используйте это как самый первый шаг перед упражнениями, если на клиенте ещё нет raw_id.
    """
    draft = get_or_create_draft(db, user.id)
    return make_success_response(result=WantsRawPublic.from_orm(draft))


@router.get(
    "/raw",
    response_model=StandardResponse,
    summary="Получить текущий draft wants_raw",
    description=(
        "Возвращает текущий `draft` wants_raw.\n\n"
        "Если draft ещё не создавался — вернёт 404. В этом случае сначала вызовите POST `/wants/raw`."
    ),
)
def get_draft_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Получить текущий `draft` wants_raw.

    Отличие от POST `/wants/raw`:
    - GET не создаёт запись (удобно, когда хотите явно понимать, есть ли draft)
    - POST создаёт, если draft отсутствует
    """
    draft = get_draft(db, user.id)
    if draft is None:
        raise APIError(
            code="WANTS_DRAFT_NOT_FOUND",
            http_code=404,
            message="Draft wants_raw не найден. Создайте через POST /wants/raw.",
        )
    return make_success_response(result=WantsRawPublic.from_orm(draft))


@router.post(
    "/stream/start",
    response_model=StandardResponse,
    summary="Старт упражнения: поток 'Я хочу'",
    description=(
        "Помечает старт упражнения **'Поток Я хочу'**.\n\n"
        "Что делает:\n"
        "- создаёт draft wants_raw, если его ещё нет\n"
        "- ставит `stream_started_at = now()` (только если ещё не установлен)\n"
        "- возвращает `stream_timer_seconds` (по умолчанию 600)\n\n"
        "Про 600 секунд:\n"
        "- это **рекомендуемая длительность** упражнения (10 минут) для UI/клиента\n"
        "- сервер **не ограничивает** приём текста по таймеру (это подсказка/таймер для интерфейса)\n"
    ),
)
def stream_start_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Старт упражнения 'Поток Я хочу'.

    Используется, чтобы:
    - зафиксировать момент старта (аналитика/таймлайн)
    - отдать клиенту рекомендуемый таймер (`stream_timer_seconds`)
    """
    wants_raw = start_stream(db, user.id)
    result = WantsStreamStartPublic(
        raw_id=wants_raw.id,
        stream_started_at=wants_raw.stream_started_at,
        stream_timer_seconds=wants_raw.stream_timer_seconds,
        stream_completed_at=wants_raw.stream_completed_at,
    )
    return make_success_response(result=result)


@router.post(
    "/stream/append",
    response_model=StandardResponse,
    summary="Поток: добавить строку (или завершить словом 'стоп')",
    description=(
        "Добавляет очередную строку/мысль в упражнение **'Поток Я хочу'**.\n\n"
        "Правила:\n"
        "- если draft не существует — будет создан автоматически\n"
        "- если поток ещё не стартовал — `stream_started_at` будет установлен автоматически\n"
        "- текст дописывается в `raw_wants_stream` (через `\\n`)\n"
        "- дополнительно создаётся запись в `wants_raw_chunks` (exercise=`stream`)\n\n"
        "Автозавершение:\n"
        "- если `text` равен `стоп` или `stop` (trim + casefold), то упражнение завершается:\n"
        "  - выставляется `stream_completed_at`\n"
        "  - chunk **не** создаётся\n"
    ),
)
def stream_append_view(
    payload: WantsTextIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Добавить строку в поток.

    Для клиента это основной эндпоинт во время упражнения: вызывается много раз.
    """
    wants_raw, is_completed = append_stream_text(db, user.id, payload.text)
    result = WantsStreamAppendPublic(
        raw_id=wants_raw.id,
        is_completed=is_completed,
        raw_wants_stream_preview=_preview(wants_raw.raw_wants_stream),
    )
    return make_success_response(result=result)


@router.post(
    "/stream/finish",
    response_model=StandardResponse,
    summary="Поток: принудительно завершить",
    description=(
        "Принудительно завершает упражнение **'Поток Я хочу'**.\n\n"
        "Что именно 'заканчивает':\n"
        "- ставит `stream_completed_at = now()` (если ещё не установлен)\n\n"
        "Зачем нужно:\n"
        "- когда пользователь нажал кнопку 'Закончить' в UI\n"
        "- когда таймер на клиенте истёк, но пользователь не отправил 'стоп'\n\n"
        "Важно:\n"
        "- этот эндпоинт **не** проверяет, что текст заполнен; это просто отметка 'упражнение завершено'\n"
    ),
)
def stream_finish_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Завершить поток без отправки ключевого слова.

    Это просто отметка завершения (`stream_completed_at`).
    """
    wants_raw = finish_stream(db, user.id)
    result = WantsStreamStartPublic(
        raw_id=wants_raw.id,
        stream_started_at=wants_raw.stream_started_at,
        stream_timer_seconds=wants_raw.stream_timer_seconds,
        stream_completed_at=wants_raw.stream_completed_at,
    )
    return make_success_response(result=result)


@router.put(
    "/future-me",
    response_model=StandardResponse,
    summary="Мне 40: установить текст целиком",
    description=(
        "Сохраняет текст упражнения **'Мне 40'** целиком.\n\n"
        "Что делает:\n"
        "- создаёт draft wants_raw, если его ещё нет\n"
        "- перезаписывает поле `raw_future_me`\n\n"
        "Если хотите писать частями (параграфами) — используйте POST `/wants/future-me/append`."
    ),
)
def future_me_set_view(
    payload: WantsFutureMeSetIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Установить текст упражнения 'Мне 40' целиком (перезапись).
    """
    wants_raw = set_future_me(db, user.id, payload.text)
    result = WantsFutureMePublic(
        raw_id=wants_raw.id,
        raw_future_me=wants_raw.raw_future_me,
        future_me_completed_at=wants_raw.future_me_completed_at,
    )
    return make_success_response(result=result)


@router.post(
    "/future-me/append",
    response_model=StandardResponse,
    summary="Мне 40: дописать текст (chunk)",
    description=(
        "Дописать текст в упражнение **'Мне 40'**.\n\n"
        "Что делает:\n"
        "- создаёт draft wants_raw, если его ещё нет\n"
        "- дописывает `\\n{text}` в `raw_future_me`\n"
        "- создаёт запись в `wants_raw_chunks` (exercise=`future_me`)\n"
    ),
)
def future_me_append_view(
    payload: WantsTextIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Добавить chunk в 'Мне 40' (удобно для поэтапного ввода текста).
    """
    wants_raw = append_future_me_text(db, user.id, payload.text)
    result = WantsFutureMePublic(
        raw_id=wants_raw.id,
        raw_future_me=wants_raw.raw_future_me,
        future_me_completed_at=wants_raw.future_me_completed_at,
    )
    return make_success_response(result=result)


@router.post(
    "/future-me/finish",
    response_model=StandardResponse,
    summary="Мне 40: завершить упражнение",
    description=(
        "Помечает упражнение **'Мне 40'** как завершённое.\n\n"
        "Что делает:\n"
        "- ставит `future_me_completed_at = now()` (если ещё не установлен)\n\n"
        "Важно:\n"
        "- этот эндпоинт не валидирует содержимое текста; финальная валидация — в POST `/wants/complete`."
    ),
)
def future_me_finish_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Завершить упражнение 'Мне 40' (отметка времени завершения).
    """
    wants_raw = finish_future_me(db, user.id)
    result = WantsFutureMePublic(
        raw_id=wants_raw.id,
        raw_future_me=wants_raw.raw_future_me,
        future_me_completed_at=wants_raw.future_me_completed_at,
    )
    return make_success_response(result=result)


@router.put(
    "/reverse",
    response_model=StandardResponse,
    summary="Reverse: сохранить ответы на 3 вопроса",
    description=(
        "Сохраняет ответы на блок **Reverse questions** (3 вопроса):\n"
        "- `raw_envy` (зависть)\n"
        "- `raw_regrets` (сожаления)\n"
        "- `raw_what_to_do_5y` (что делать 5 лет)\n\n"
        "Особенности:\n"
        "- можно отправлять частично (например, сначала заполнить 1 поле)\n"
        "- когда все 3 поля заполнены непустыми значениями, автоматически ставится `reverse_completed_at`\n\n"
        "Зачем нужен отдельный эндпоинт:\n"
        "- это отдельный шаг wants, который мы отслеживаем как 'готов/не готов'\n"
        "- на фронте удобно сохранять ответы одним запросом\n"
    ),
)
def reverse_update_view(
    payload: WantsReverseUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Обновить reverse-ответы.

    Этот шаг считается завершённым, когда заполнены все 3 ответа (ставится reverse_completed_at).
    """
    wants_raw = update_reverse(db, user.id, payload.model_dump())
    result = WantsReversePublic(
        raw_id=wants_raw.id,
        raw_envy=wants_raw.raw_envy,
        raw_regrets=wants_raw.raw_regrets,
        raw_what_to_do_5y=wants_raw.raw_what_to_do_5y,
        reverse_completed_at=wants_raw.reverse_completed_at,
    )
    return make_success_response(result=result)


@router.get(
    "/progress",
    response_model=StandardResponse,
    summary="Прогресс wants по текущему draft",
    description=(
        "Возвращает 'чеклист' готовности по трём упражнениям.\n\n"
        "Зачем нужен:\n"
        "- фронту не нужно разбирать все поля wants_raw, чтобы понять прогресс\n"
        "- удобно для экранов прогресса/онбординга (галочки, следующий шаг)\n\n"
        "`stream_done` = есть `stream_completed_at`\n"
        "`future_me_done` = есть `future_me_completed_at`\n"
        "`reverse_done` = есть `reverse_completed_at`\n"
        "`all_done` = все три одновременно\n"
    ),
)
def wants_progress_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Прогресс wants.

    Возвращает только статусы/флаги готовности (без тяжёлых текстов), чтобы клиенту было проще.
    """
    wants_raw = get_or_create_draft(db, user.id)
    stream_done = wants_raw.stream_completed_at is not None
    future_me_done = wants_raw.future_me_completed_at is not None
    reverse_done = wants_raw.reverse_completed_at is not None
    result = WantsProgressPublic(
        raw_id=wants_raw.id,
        status=wants_raw.status,
        stream_done=stream_done,
        future_me_done=future_me_done,
        reverse_done=reverse_done,
        all_done=stream_done and future_me_done and reverse_done,
    )
    return make_success_response(result=result)


@router.post(
    "/complete",
    response_model=StandardResponse,
    summary="Завершить wants (status=completed)",
    description=(
        "Финализирует wants: проверяет, что все 3 упражнения заполнены и завершены, "
        "и переводит запись в `status=completed`.\n\n"
        "Проверки:\n"
        "- поток: должен быть `stream_completed_at` и непустой `raw_wants_stream`\n"
        "- мне 40: должен быть `future_me_completed_at` и непустой `raw_future_me`\n"
        "- reverse: должен быть `reverse_completed_at` и все 3 поля непустые\n\n"
        "Ошибки:\n"
        "- 422 `WANTS_RAW_NOT_READY` + `fields` с перечнем недостающих частей\n\n"
        "После завершения:\n"
        "- запись становится неизменяемой (любые попытки менять её вернут 409)\n"
    ),
)
def wants_complete_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Завершить wants.

    Это единственная точка, где мы строго валидируем, что wants действительно готов.
    """
    wants_raw = complete_wants(db, user.id)
    return make_success_response(result=WantsRawPublic.from_orm(wants_raw))


@router.post(
    "/analyze",
    response_model=StandardResponse,
    dependencies=[Depends(check_text_quota)],
    summary="Analyze wants via AI",
    description=(
        "Triggers AI analysis for the latest completed wants_raw and returns "
        "the persisted wants_analysis payload."
    ),
)
def wants_analyze_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    task = celery_app.send_task("wants.analyze", args=[str(user.id)])
    timeout_seconds = settings.ai_proxy_timeout_seconds + 30
    try:
        result = task.get(timeout=timeout_seconds)
    except CeleryTimeoutError:
        raise APIError(
            code="WANTS_AI_TIMEOUT",
            http_code=504,
            message="AI analysis timed out.",
        )

    if not result or not result.get("ok"):
        error = (result or {}).get("error") or {}
        raise APIError(
            code=error.get("code", "WANTS_AI_FAILED"),
            http_code=error.get("http_code", 500),
            message=error.get("message", "AI analysis failed."),
        )

    analysis = (
        WantsAnalysisPublic.model_validate(result["analysis"]).model_dump(mode="json")
    )
    return make_success_response(result=analysis)


@router.get(
    "/analysis",
    response_model=StandardResponse,
    summary="Get latest wants analysis",
    description="Returns the latest wants_analysis record for the current user.",
)
def wants_analysis_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    analysis = get_latest_analysis(db, user.id)
    if analysis is None:
        return make_success_response(result=None)
    payload = WantsAnalysisPublic.model_validate(analysis).model_dump(mode="json")
    return make_success_response(result=payload)


@router.get(
    "/history",
    response_model=StandardResponse,
    summary="История completed wants_raw (пагинация)",
    description=(
        "Возвращает список `completed` wants_raw записей текущего пользователя.\n\n"
        "Пагинация:\n"
        "- `page` (по умолчанию 1)\n"
        "- `page_size` (по умолчанию 20)\n\n"
        "Результат:\n"
        "- `result.items` содержит массив wants_raw\n"
        "- `meta.pagination` содержит расчёт пагинации\n"
    ),
)
def wants_history_view(
    page: int = Query(1, ge=1, description="Номер страницы (1..)."),
    page_size: int = Query(20, ge=1, le=100, description="Размер страницы (1..100)."),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    История завершённых wants.
    """
    items, total = get_history_page(
        db=db,
        user_id=user.id,
        page=page,
        page_size=page_size,
    )

    result_items: List[Dict[str, Any]] = [
        WantsRawPublic.from_orm(i).model_dump() for i in items
    ]
    payload: Dict[str, Any] = {"items": result_items}

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1
    pagination = Pagination(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
    return make_success_response(
        result=jsonable_encoder(payload),
        pagination=pagination,
    )


@router.get(
    "/raw/{raw_id}",
    response_model=StandardResponse,
    summary="Получить completed wants_raw по id",
    description=(
        "Возвращает **только completed** wants_raw по `raw_id`.\n\n"
        "Зачем:\n"
        "- просмотр истории/деталей конкретного завершённого wants\n\n"
        "Важно:\n"
        "- user-scoped: можно получить только свою запись\n"
        "- draft здесь не возвращается (для draft используйте GET `/wants/raw`)\n"
    ),
)
def wants_raw_by_id_view(
    raw_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Получить конкретный completed wants_raw.
    """
    wants_raw = get_completed_by_id(db, user.id, raw_id)
    if wants_raw is None:
        raise APIError(
            code="WANTS_RAW_NOT_FOUND",
            http_code=404,
            message="wants_raw не найден.",
        )
    return make_success_response(result=WantsRawPublic.from_orm(wants_raw))


__all__ = ["router"]
