FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/api/requirements.txt /tmp/api-requirements.txt
COPY services/ml/requirements.txt /tmp/ml-requirements.txt
COPY services/worker/requirements.txt /tmp/worker-requirements.txt
RUN pip install --no-cache-dir -r /tmp/api-requirements.txt -r /tmp/ml-requirements.txt -r /tmp/worker-requirements.txt

COPY . /app
ENV PYTHONPATH=/app/services/api:/app/services/ml:/app/services/worker

CMD ["celery", "-A", "worker.tasks", "worker", "--loglevel=INFO", "-Q", "captures"]
