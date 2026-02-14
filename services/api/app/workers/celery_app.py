from __future__ import annotations

import os

from celery import Celery

celery_app = Celery(
    "aesthetica",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
)

celery_app.conf.update(
    task_routes={"worker.tasks.process_capture": {"queue": "captures"}},
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
