import os
from celery import Celery
from django.conf import settings
import importlib
from celery.signals import task_prerun
from django import db

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "swiftsuite.settings")

app = Celery("app")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Merge schedules from each app
app.conf.beat_schedule = {}

for app_name in settings.INSTALLED_APPS:
    try:
        mod = importlib.import_module(f"{app_name}.celery_schedule")
        if hasattr(mod, "APP_CELERY_BEAT_SCHEDULE"):
            app.conf.beat_schedule.update(mod.APP_CELERY_BEAT_SCHEDULE)
    except ModuleNotFoundError:
        pass

@task_prerun.connect
def close_db_connections(**kwargs):
    db.connections.close_all()