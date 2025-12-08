from celery.schedules import crontab

APP_CELERY_BEAT_SCHEDULE = {
    "sync-ebay-every-half-hour": {
        "task": "inventoryApp.tasks.sync_ebay_inventory_task",
        "schedule": crontab(minute=0, hour="*/30"),
    },
    "update-ebay-price-quantity-30min": {
        "task": "inventoryApp.tasks.update_ebay_price_quantity_inventory_task",
        "schedule": crontab(minute=0, hour="*/30"),
    },
    "check-ebay-item-ended-30min": {
        "task": "inventoryApp.tasks.check_ebay_item_ended_task",
        "schedule": crontab(minute=0, hour="*/30"),
    }
}
