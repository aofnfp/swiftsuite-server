from celery.schedules import crontab
from celery.signals import task_prerun
from django import db

APP_CELERY_BEAT_SCHEDULE = {
    "sync-ebay-every-half-hour": {
        "task": "inventoryApp.tasks.sync_ebay_inventory_task",
        "schedule": crontab(minute="*/30"),
    },
    "update-ebay-price-quantity-30min": {
        "task": "inventoryApp.tasks.update_ebay_price_quantity_inventory_task",
        "schedule": crontab(minute="*/30"),
    },
    "check-ebay-item-ended-30min": {
        "task": "inventoryApp.tasks.check_ebay_item_ended_task",
        "schedule": crontab(minute="*/30"),
    }
}


@task_prerun.connect
def close_db_connections(**kwargs):
    db.connections.close_all()
