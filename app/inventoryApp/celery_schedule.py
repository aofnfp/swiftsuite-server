from celery.schedules import crontab

APP_CELERY_BEAT_SCHEDULE = {
    "sync-ebay-every-half-hour": {
        "task": "inventoryApp.tasks.sync_ebay_inventory_task",
        "schedule": crontab(minute=0, hour="*/30"),
    }
}
