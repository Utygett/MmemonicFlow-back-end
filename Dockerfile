FROM python:3.13-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

# Alembic файлы (лежат рядом с Dockerfile)
COPY alembic.ini .
COPY migrations ./migrations
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app/backend

CMD ["/app/entrypoint.sh"]
