# installer-service

HTTP-сервис на FastAPI, который по запросу с конфигом запускает GitHub Actions workflow `build-installer.yml`, ждёт завершения, скачивает артефакт `agent_installer.exe` и отдаёт клиенту.

## Как это работает

1. Клиент отправляет `POST /builds` с параметрами конфига (например, `server_url`)
2. Сервис диспатчит `workflow_dispatch` на `build-installer.yml` с переданными inputs
3. Workflow собирает инсталлятор, записывает `config.json` внутрь дистрибутива
4. Сервис поллит GitHub API каждые 15 сек, ждёт завершения run
5. После успеха скачивает zip-артефакт, распаковывает `agent_installer.exe`
6. Файл сохраняется на диске, клиент может скачать его через `GET /builds/{id}/download`

Записи о сборках удаляются автоматически через 72 часа (TTL настраивается).

## Требования

- Docker + Docker Compose
- GitHub PAT с правами `Actions: Read and write` на репозиторий

## Запуск

```bash
cp .env.example .env
# заполнить .env (см. раздел "Переменные окружения")
docker compose up --build
```

После старта API доступен на `http://localhost:8000`.

## Переменные окружения

| Переменная | Обязательная | Описание |
|------------|:---:|---------|
| `DATABASE_URL` | да | Устанавливается автоматически docker-compose |
| `GITHUB_TOKEN` | да | PAT с `Actions: Read and write` |
| `GITHUB_OWNER` | да | Владелец репозитория (username или org) |
| `GITHUB_REPO` | да | Имя репозитория (например, `AWClientNew`) |
| `INSTALLER_DIR` | нет | Путь для хранения файлов (по умолч. `/data/installers`) |
| `INSTALLER_TTL_HOURS` | нет | Время жизни сборки в часах (по умолч. `72`) |

### Как получить GITHUB_TOKEN

1. GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens**
2. **Repository access**: выбрать только нужный репозиторий
3. **Permissions → Repository permissions → Actions**: `Read and write`
4. Скопировать токен в `.env`

## API

### POST /builds

Создать новую сборку.

**Тело запроса:**
```json
{
  "server_url": "https://your-server.com"
}
```

**Ответ 202:**
```json
{
  "id": "92bcf9a4-cdbc-443b-a8f2-33e68d84e561",
  "status": "pending",
  "created_at": "2026-03-20T06:28:08.366130Z"
}
```

### GET /builds/{id}

Получить статус сборки.

**Возможные статусы:**

| Статус | Описание |
|--------|---------|
| `pending` | Принято, отправка в GitHub |
| `queued` | Workflow задиспатчен, ждём появления run |
| `running` | Run найден, идёт сборка |
| `success` | Готово, файл доступен для скачивания |
| `failed` | Ошибка (поле `error` содержит причину) |

**Ответ 200:**
```json
{
  "id": "92bcf9a4-cdbc-443b-a8f2-33e68d84e561",
  "status": "running",
  "gh_run_id": 23331935755,
  "error": null,
  "created_at": "2026-03-20T06:28:08.366130Z",
  "updated_at": "2026-03-20T06:28:09.360669Z",
  "expires_at": "2026-03-23T06:28:08.235301Z"
}
```

### GET /builds/{id}/download

Скачать `agent_installer.exe`. Доступен только при `status=success`.

**Ответы:**
- `200` — бинарный файл `agent_installer.exe`
- `409` — сборка ещё не готова
- `410` — файл уже удалён (истёк TTL)

## Пример использования

```bash
# 1. Создать сборку
curl -X POST http://localhost:8000/builds \
  -H "Content-Type: application/json" \
  -d '{"server_url": "https://example.com"}' \
  | jq .

# 2. Проверять статус (~3 мин на полный цикл)
curl http://localhost:8000/builds/<id> | jq .

# 3. Скачать после status=success
curl -O http://localhost:8000/builds/<id>/download
```

## Структура проекта

```
installer-service/
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── pyproject.toml
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 0001_create_builds_table.py
└── app/
    ├── main.py        # FastAPI app + lifespan
    ├── config.py      # pydantic-settings
    ├── database.py    # SQLAlchemy async engine
    ├── models.py      # ORM: Build
    ├── schemas.py     # Pydantic request/response
    ├── crud.py        # DB helpers
    ├── github.py      # httpx GitHub API client
    ├── worker.py      # Background task state machine
    ├── cleanup.py     # TTL cleanup coroutine
    └── routers/
        └── builds.py  # POST/GET /builds
```

## Схема БД

Таблица `builds`:

| Поле | Тип | Описание |
|------|-----|---------|
| `id` | UUID PK | Генерируется сервером |
| `status` | VARCHAR(20) | pending → queued → running → success/failed |
| `config` | JSONB | Переданные параметры конфига |
| `gh_run_id` | BIGINT | ID запуска в GitHub Actions |
| `artifact_path` | TEXT | Путь к скачанному файлу на диске |
| `error` | TEXT | Сообщение об ошибке |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |
| `expires_at` | TIMESTAMPTZ | `created_at + TTL` |
