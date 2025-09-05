from celery.schedules import crontab

APP_CELERY_BEAT_SCHEDULE = {
    "reload_all_vendors": {
        "task": "vendorActivities.tasks.reload_all_vendors",
        "schedule": crontab(hour=2, minute=0),  # run daily at 2 AM
    }
}

