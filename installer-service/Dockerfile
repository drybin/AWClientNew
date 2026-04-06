FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    "fastapi>=0.111.0" \
    "uvicorn[standard]>=0.29.0" \
    "sqlalchemy[asyncio]>=2.0.0" \
    "asyncpg>=0.29.0" \
    "alembic>=1.13.0" \
    "httpx>=0.27.0" \
    "pydantic-settings>=2.2.0"

COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
