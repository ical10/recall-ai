from celery import Celery

from app.core.celery_app import celery_app


def test_celery_app_is_celery_instance():
    assert isinstance(celery_app, Celery)


def test_celery_app_uses_redis_broker_and_backend():
    assert celery_app.conf.broker_url.startswith("redis://")
    assert celery_app.conf.result_backend.startswith("redis://")


def test_celery_app_uses_json_serialization_and_utc():
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]
    assert celery_app.conf.timezone == "UTC"
    assert celery_app.conf.enable_utc is True
