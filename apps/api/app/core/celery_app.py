from celery import Celery

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
)
