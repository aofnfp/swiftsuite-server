from celery.schedules import crontab
from celery.signals import task_prerun
from django import db

APP_CELERY_BEAT_SCHEDULE = {
    "sync-ebay-every-eight-hour": {
        "task": "inventoryApp.tasks.download_marketplace_items_to_inventory_task",
        "schedule": crontab(hour="*/8"),
    },
    "update-ebay-price-quantity-30min": {
        "task": "inventoryApp.tasks.update_ebay_price_quantity_inventory_task",
        "schedule": crontab(minute="*/30"),
    },
    "check-ebay-item-ended-30min": {
        "task": "inventoryApp.tasks.check_ebay_item_ended_task",
        "schedule": crontab(minute="*/30"),
    },
    "map-marketplace-items-to-vendor-4hr": {
        "task": "inventoryApp.tasks.map_marketplace_items_to_vendor_task",
        "schedule": crontab(hour="*/4"),
    },
}


@task_prerun.connect
def close_db_connections(**kwargs):
    db.connections.close_all()
