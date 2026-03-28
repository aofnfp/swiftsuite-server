from celery.schedules import crontab

APP_CELERY_BEAT_SCHEDULE = {
    "reload_all_vendors": {
        "task": "vendorActivities.tasks.reload_all_vendors",
        "schedule": crontab(minute=0, hour='*/6'),  # Every 6 hours
    }
}

