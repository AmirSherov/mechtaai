Ок, делаем **чистый wants без AI**: только сбор данных 3 упражнений, хранение в Postgres и нормальная API-логика. По ТЗ “поток желаний” — это **3 базовых упражнения до постановки целей**, ответы сохраняем в `WantsRaw`, дальше уже сверху можно навесить AI (потом).

Ниже — готовый **MD-файл** (можешь прямо сохранить как `WANTS.md`).

````md
# Wants (без AI) — спецификация модуля

## 1) Зачем нужен Wants
Wants — это модуль “достать реальные желания”, обходя внутреннего цензора, ДО целей и планов.
Пользователь проходит 3 упражнения:
1) Поток “Я хочу…” (в идеале 10 минут, ввод только “добавлять”, без редактирования) 
2) “Мне 40 лет” / “Будущая версия” — текст в настоящем времени (можно частями) 
3) Reverse questions — 3 вопроса: зависть / сожаления / что успеть за 5 лет 

Все ответы сохраняются в БД как сырые тексты (`WantsRaw`), чтобы потом:
- показывать пользователю “сводку” (минимум: что он написал)
- использовать эти данные в следующих модулях (история 3–5 лет, цели) 

> Важно: в ТЗ для бота поток может собираться “сообщениями до слова ‘Готово’”, без спама обратной связью. 


## 2) Данные (PostgreSQL)

### 2.1 Таблица wants_raw
Хранит “сырые” ответы 3 упражнений. По ТЗ — именно сюда пишем всё. 

**wants_raw**
- id: UUID (PK)
- user_id: UUID (FK -> users.id)
- status: enum('draft','completed') default 'draft'

**Поток “Я хочу”**
- stream_started_at: timestamptz nullable (бек фиксирует старт) :contentReference[oaicite:7]{index=7}
- stream_timer_seconds: int default 600 (опционально)
- raw_wants_stream: text nullable
- stream_completed_at: timestamptz nullable

**“Мне 40”**
- raw_future_me: text nullable
- future_me_completed_at: timestamptz nullable

**Reverse questions**
- raw_envy: text nullable
- raw_regrets: text nullable
- raw_what_to_do_5y: text nullable
- reverse_completed_at: timestamptz nullable

**Служебное**
- completed_at: timestamptz nullable (когда все упражнения завершены)
- created_at: timestamptz
- updated_at: timestamptz

Индексы:
- idx_wants_raw_user_updated (user_id, updated_at desc)
- (рекомендовано) уникальный draft на пользователя:
  UNIQUE(user_id) WHERE status='draft'

---

### 2.2 (Опционально) wants_raw_chunks
Если хочешь реально строго “только добавлять” и собирать сообщения как в боте (до “Готово”), можно хранить куски отдельно.

**wants_raw_chunks**
- id: UUID
- wants_raw_id: UUID FK -> wants_raw.id
- exercise: enum('stream','future_me')  (reverse обычно по одному ответу, без чанков)
- text: text
- created_at: timestamptz

Плюс: из chunks можно всегда собрать `raw_wants_stream/raw_future_me`, и ты никогда не потеряешь исходный поток.


## 3) Логика работы (без AI)

### 3.1 Стейт-машина
- У пользователя есть **один активный draft WantsRaw**
- Упражнения можно проходить в любом порядке (в UI — меню из 3 кнопок) :contentReference[oaicite:8]{index=8}
- “Завершить wants” можно только когда заполнены все части:
  - raw_wants_stream
  - raw_future_me
  - raw_envy
  - raw_regrets
  - raw_what_to_do_5y :contentReference[oaicite:9]{index=9}

### 3.2 Поток “Я хочу”
ТЗ допускает 2 режима: простой (без жесткого таймера) и жесткий (бек следит за временем). :contentReference[oaicite:10]{index=10}  
Для API проще и надежнее:
- `start` фиксирует время старта (stream_started_at)
- `append` добавляет текст (или chunk)
- если пришло сообщение `Готово` — фиксируем завершение и закрываем поток 

Редактирование “назад” на уровне API можно запретить, если используешь chunks.

### 3.3 “Мне 40”
Похожая логика: можно текстом целиком или частями, завершение — по отдельному `finish` или по слову “Готово”. 

### 3.4 Reverse questions
3 ответа сохраняются в 3 поля. В UI — “каждый вопрос отдельный экран”, но на API это просто:
- PUT одним запросом все 3
или
- PUT по одному (envy/regrets/what_to_do_5y) :contentReference[oaicite:13]{index=13}


## 4) API эндпоинты (FastAPI)

База: `/api/v1/wants`

### 4.1 Draft: создать/получить
#### POST /api/v1/wants/raw
Создаёт draft WantsRaw (если уже есть — возвращает существующий).

**Response 200**
```json
{
  "success": true,
  "data": { "id": "...", "status": "draft", "...": "..." }
}
````

#### GET /api/v1/wants/raw

Возвращает текущий draft (или 404 если нет; но лучше делать auto-create через POST).

---

### 4.2 Поток “Я хочу”

#### POST /api/v1/wants/stream/start

* Создаёт draft (если нет)
* Ставит `stream_started_at=now()`
* (опционально) `stream_timer_seconds=600`

**Response**

```json
{
  "success": true,
  "data": {
    "raw_id": "...",
    "stream_started_at": "2025-12-15T10:00:00Z",
    "stream_timer_seconds": 600,
    "stream_completed_at": null
  }
}
```

#### POST /api/v1/wants/stream/append

Body:

```json
{ "text": "Я хочу ..."}
```

Логика:

* если `text` == "готово" (trim + casefold) → завершить поток
* иначе добавить:

  * либо в `raw_wants_stream` (конкат с \n)
  * либо в `wants_raw_chunks`

**Response**

```json
{
  "success": true,
  "data": {
    "raw_id": "...",
    "is_completed": false,
    "raw_wants_stream_preview": "Я хочу...\n..."
  }
}
```

#### POST /api/v1/wants/stream/finish

Явное завершение (если не хочешь ловить слово “Готово” на API).

---

### 4.3 “Мне 40”

#### PUT /api/v1/wants/future-me

Body:

```json
{ "text": "Мне 40. Я живу..." }
```

Сохраняет `raw_future_me`.

**Response**

```json
{ "success": true, "data": { "raw_id": "...", "raw_future_me": "..." } }
```

#### POST /api/v1/wants/future-me/append

Если делаешь чанки — аналогично stream/append.

#### POST /api/v1/wants/future-me/finish

Ставит `future_me_completed_at`.

---

### 4.4 Reverse questions

#### PUT /api/v1/wants/reverse

Body:

```json
{
  "raw_envy": "...",
  "raw_regrets": "...",
  "raw_what_to_do_5y": "..."
}
```

Сохраняет ответы и ставит `reverse_completed_at`, если все 3 поля заполнены.

---

### 4.5 Прогресс и завершение wants

#### GET /api/v1/wants/progress

Возвращает “готовность” по частям — удобно для фронта/бота.

**Response**

```json
{
  "success": true,
  "data": {
    "raw_id": "...",
    "status": "draft",
    "stream_done": true,
    "future_me_done": false,
    "reverse_done": true,
    "all_done": false
  }
}
```

#### POST /api/v1/wants/complete

Проверяет, что заполнены все поля (5 штук) и ставит:

* status='completed'
* completed_at=now()

Если чего-то не хватает → 422 с деталями полей.

---

### 4.6 История (опционально, но полезно)

#### GET /api/v1/wants/history

Список completed WantsRaw (пагинация).

#### GET /api/v1/wants/raw/{raw_id}

Получить конкретный completed набор (только владельцу).

---

## 5) Правила доступа и валидации

* Все wants-данные **строго user-scoped**: пользователь видит только своё
* Нельзя изменять completed запись (только читать)
* Поток “Я хочу” по ТЗ — “только добавлять” (лучше enforce через chunks) 
* Для бота: поток собираем до слова “Готово”
