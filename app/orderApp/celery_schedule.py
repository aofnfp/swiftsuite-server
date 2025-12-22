from celery.schedules import crontab

APP_CELERY_BEAT_SCHEDULE = {
    "sync-ebay-every-half-hour": {
        "task": "orderApp.tasks.sync_ebay_order_task",
        "schedule": crontab(minute="*/35"),
    }
}
