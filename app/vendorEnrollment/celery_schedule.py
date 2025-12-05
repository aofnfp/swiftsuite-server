from celery.schedules import crontab

APP_CELERY_BEAT_SCHEDULE = {
    "update_all_enrollments": {
        "task": "vendorEnrollment.tasks.update_all_enrollments",
        "schedule": crontab(hour=2, minute=0),  # Every day at 2:00 AM
    }
}