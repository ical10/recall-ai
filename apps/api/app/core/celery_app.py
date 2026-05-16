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
            # 19:00 UTC = 02:00 WIB — true overnight for the current solo user.
            "schedule": crontab(hour=19, minute=0),
            "kwargs": {"batch_size": 25},
        },
        "content-gen-shared-pool": {
            "task": "content_gen.generate_shared_pool",
            # 18:00 UTC, one hour before the enrichment tick so any unenriched
            # rows we generate get a safety-net pass the same evening.
            "schedule": crontab(hour=18, minute=0),
            "kwargs": {"count": 10},
        },
    },
)
