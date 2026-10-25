# Multi-stage lightweight Python 3.11 container for HaemoPulse Unified Backend + ML Service
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source and trained ML model artifacts
COPY backend/ ./backend/
COPY ml_service/ ./ml_service/

WORKDIR /app/backend

# Default port is 8000 (overridden by $PORT in cloud environments like Render/Koyeb)
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]
