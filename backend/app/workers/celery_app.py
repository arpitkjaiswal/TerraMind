"""
Celery application — async task queue for document ingestion and memify.

Two queues:
  - cognify: Cognee extract+cognify pipeline (slow, LLM-heavy)
  - memify:  Scheduled batch re-processing of corrections

Workers run separately from the API process so slow document
processing doesn't block API response time.
"""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "aegis",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,           # re-queue on worker crash
    worker_prefetch_multiplier=1,  # one task at a time per worker (LLM calls are heavy)
    task_routes={
        "app.workers.tasks.cognify_document": {"queue": "cognify"},
        "app.workers.tasks.run_memify_batch": {"queue": "memify"},
    },
    beat_schedule={
        "nightly-memify": {
            "task": "app.workers.tasks.run_memify_batch",
            "schedule": 86400.0,   # every 24 hours
            "options": {"queue": "memify"},
        },
    },
    task_soft_time_limit=600,      # 10 min soft limit per cognify task
    task_time_limit=900,           # 15 min hard limit
)
