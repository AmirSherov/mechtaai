# Запуск MechtaAI (API + BG worker)

Все команды запускать из корня репозитория `E:\projects\mechtaai` (там где `manage.py`).

## Вариант A: Docker Compose (рекомендовано)

Поднимет `redis`, `web` (API) и `worker` (BG):

```powershell
docker compose up --build
```

API будет доступен на `http://localhost:8000`, Swagger: `http://localhost:8000/docs`.

Остановить:

```powershell
docker compose down
```

## Вариант B: Локально в venv (Windows)

### 1) Активировать venv

```powershell
.\venv\Scripts\Activate.ps1
```

### 2) Запустить Redis (нужен и для API, и для worker)

Самый простой способ — Redis в Docker:

```powershell
docker run --rm -p 6379:6379 --name mechtaai-redis redis:7-alpine
```

Оставь этот терминал открытым.

### 3) Применить миграции

```powershell
python manage.py upgrade
```

### 4) Запустить API (FastAPI)

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5) Запустить BG worker (Celery)

В отдельном терминале (venv активирован, Redis уже запущен):

```powershell
python -m mechtaai_bg_worker.main
```

## Проверка

- API: `GET http://localhost:8000/`
- Swagger: `http://localhost:8000/docs`

 