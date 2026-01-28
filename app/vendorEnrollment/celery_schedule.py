from celery.schedules import crontab

APP_CELERY_BEAT_SCHEDULE = {
    "update_all_enrollments": {
        "task": "vendorEnrollment.tasks.update_all_enrollments",
        "schedule": crontab(minute=0, hour='*/6'),  # Every 6 hours
    }
}