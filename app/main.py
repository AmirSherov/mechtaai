from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import text

from app.core.auth.api.v1.routes_auth import router as auth_router
from app.core.auth.api.v1.routes_me import router as me_router
from app.core.areas.api.v1.routes_areas import router as areas_router
from app.core.future_story.api.v1.routes_future_story import (
    router as future_story_router,
)
from app.core.generate_goals.api.v1.routes_goals import (
    router as goals_router,
)
from app.core.plan_steps.api.v1.routes_steps import (
    router as steps_router,
)
from app.core.rituals.api.v1.routes_rituals import (
    router as rituals_router,
)
from app.core.visuals.api.v1.routes_visuals import (
    router as visuals_router,
)
from app.core.gamification.api.v1.routes_gamification import (
    router as gamification_router,
)
from app.core.life_wheel.api.v1.routes_life_wheel import (
    router as life_wheel_router,
)
from app.core.wants.api.v1.routes_wants import router as wants_router
from app.database.session import SessionLocal
from app.utils.redis_client import get_redis
from mechtaai_bg_worker.celery_app import celery_app
from app.response import StandardResponse, make_error_response
from app.response.response import APIError


app = FastAPI()
try:
    uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")
except RuntimeError:
    pass


@app.exception_handler(APIError)
async def api_error_handler(
    request: Request,
    exc: APIError,
) -> JSONResponse:
    response: StandardResponse = make_error_response(
        code=exc.code,
        http_code=exc.http_code,
        message=exc.message,
        details=exc.details,
        fields=exc.fields,
    )
    return JSONResponse(
        status_code=exc.http_code,
        content=jsonable_encoder(response),
    )


app.title = "MechtaAI API"
app.version = "1.0.0"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root() -> str:
    # Health checks
    api_ok = True

    # DB
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        try:
            db.close()
        except Exception:
            pass

    # Redis
    redis_ok = False
    try:
        redis = get_redis()
        redis.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    # Celery worker
    worker_ok = False
    try:
        replies = celery_app.control.ping(timeout=0.5)
        worker_ok = bool(replies)
    except Exception:
        worker_ok = False

    def row(label: str, ok: bool) -> str:
        color = "#10B981" if ok else "#EF4444"
        text = "Online" if ok else "Offline"
        return f"""
                <div class="info-row">
                    <span>{label}</span>
                    <span style="color:{color}; font-weight:600;">{text}</span>
                </div>
        """

    status_rows = (
        row("API:", api_ok)
        + row("Database:", db_ok)
        + row("Redis:", redis_ok)
        + row("BG worker:", worker_ok)
    )

    html = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8" />
        <title>MechtaAI API - Status</title>
        <style>
            :root {
                --bg: #0F0F13;
                --card: #18181B;
                --text: #E5E5E5;
                --text-muted: #9CA3AF;
                --border: rgba(255, 255, 255, 0.08);
                --accent: #6366F1;
            }

            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: Inter, system-ui, sans-serif;
                background: var(--bg);
                color: var(--text);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }

            .container {
                text-align: center;
                background: var(--card);
                padding: 40px 40px;
                border-radius: 16px;
                border: 1px solid var(--border);
                width: 100%;
                max-width: 480px;
                box-shadow: 0 0 40px rgba(0,0,0,0.3);
                animation: fadeIn 0.6s ease;
            }

            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }

            h1 {
                font-size: 28px;
                margin-bottom: 10px;
                color: white;
                font-weight: 600;
            }

            .sub {
                font-size: 15px;
                color: var(--text-muted);
                margin-bottom: 30px;
            }

            .info-box {
                background: #111113;
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 16px;
                text-align: left;
                margin: 0 auto 26px;
                width: 100%;
            }

            .info-row {
                display: flex;
                justify-content: space-between;
                margin-bottom: 8px;
                font-size: 14px;
            }

            .info-row span:first-child {
                color: var(--text-muted);
            }

            .btn-group {
                display: flex;
                justify-content: center;
                gap: 12px;
            }

            a.btn {
                padding: 10px 20px;
                border-radius: 10px;
                text-decoration: none;
                font-size: 14px;
                border: 1px solid var(--border);
                background: #141418;
                color: var(--text);
                transition: 0.25s;
            }

            a.btn:hover {
                background: #1C1C23;
                border-color: var(--accent);
                color: var(--accent);
                transform: translateY(-1px);
            }

        </style>
    </head>
    <body>
        <div class="container">
            <h1>MechtaAI Backend</h1>
            <p class="sub">Это backend API сервиса Mechta AI.</p>

            <div class="info-box">
__STATUS_ROWS__
            </div>

            <div class="btn-group">
                <a class="btn" href="/docs">Swagger UI</a>
                <a class="btn" href="/redoc">ReDoc</a>
            </div>
        </div>
    </body>
    </html>
    """
    return html.replace("__STATUS_ROWS__", status_rows)


app.include_router(auth_router, prefix="/api/v1")
app.include_router(me_router, prefix="/api/v1")
app.include_router(areas_router, prefix="/api/v1")
app.include_router(life_wheel_router, prefix="/api/v1")
app.include_router(wants_router, prefix="/api/v1")
app.include_router(future_story_router, prefix="/api/v1")
app.include_router(goals_router, prefix="/api/v1")
app.include_router(steps_router, prefix="/api/v1")
app.include_router(rituals_router, prefix="/api/v1")
app.include_router(visuals_router, prefix="/api/v1")
app.include_router(gamification_router, prefix="/api/v1")


__all__ = ["app"]
