from celery.schedules import crontab

APP_CELERY_BEAT_SCHEDULE = {
    "sync-ebay-every-half-hour": {
        "task": "orderApp.tasks.sync_ebay_order_task",
        "schedule": crontab(minute="*/10"),
    },
    "background_refresh_access_token_9_minutes": {
        "task": "orderApp.tasks.background_refresh_access_token_task",
        "schedule": crontab(minute="*/5"),
    },
    "process_vendor_orders": {
        "task": "orderApp.tasks.process_vendor_orders",
        "schedule": crontab(minute="*/10"),
    },
    "check_vendor_orders": {
        "task": "orderApp.tasks.check_vendor_order_status",
        "schedule": crontab(minute="*/10"),
    }
}
