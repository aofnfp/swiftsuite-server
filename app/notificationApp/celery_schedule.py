from celery.schedules import crontab

APP_CELERY_BEAT_SCHEDULE = {
    "dispatch-notification-every-5min": {
        "task": "notificationApp.tasks.run_notification_dispatcher",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    }
}