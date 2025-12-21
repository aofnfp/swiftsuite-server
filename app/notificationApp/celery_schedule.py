from celery.schedules import crontab

APP_CELERY_BEAT_SCHEDULE = {
    "update_all_enrollments": {
        "task": "notificationApp.tasks.run_notification_dispatcher",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    }
}