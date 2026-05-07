from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "recall_ai",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    imports=("app.workers.content_gen",),
    beat_schedule={
        "content-gen-daily": {
            "task": "content_gen.run_daily",
            "schedule": crontab(hour=3, minute=0),
            "kwargs": {"batch_size": 25},
        },
    },
)
