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
    # Worker RAM controls (Railway cost): one prefork child, recycled to release
    # accumulated/peak memory, holding minimal prefetched work.
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    worker_max_memory_per_child=400_000,  # KB (~390 MB): recycle a bloated child
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
        "content-gen-personalized-all": {
            "task": "content_gen.generate_personalized_for_all",
            # 20:00 UTC — after the shared pool and enrichment ticks complete,
            # giving the LLM fresh exclusion context.
            "schedule": crontab(hour=20, minute=0),
            "kwargs": {"count": 5},
        },
    },
)
