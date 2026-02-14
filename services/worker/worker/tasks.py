from __future__ import annotations

import logging

from app.db.session import SessionLocal
from app.services.pipeline_executor import process_capture
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="worker.tasks.process_capture", bind=True, max_retries=3)
def process_capture_task(self, capture_id: str) -> None:
    db = SessionLocal()
    try:
        process_capture(db, capture_id)
    except Exception as exc:
        logger.exception("capture_task_failed")
        raise self.retry(exc=exc, countdown=5)
    finally:
        db.close()
