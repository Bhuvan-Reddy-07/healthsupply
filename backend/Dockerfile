FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including libgomp for lightgbm
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgomp1 \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and supporting modules
COPY backend /app/backend
COPY simulator /app/simulator
COPY ml /app/ml
COPY infra /app/infra

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
