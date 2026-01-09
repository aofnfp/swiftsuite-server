from celery.schedules import crontab
from celery.signals import task_prerun
from django import db

APP_CELERY_BEAT_SCHEDULE = {
    "download_update_marketplace_items_4_hour": {
        "task": "inventoryApp.tasks.download_update_marketplace_items_task",
        "schedule": crontab(hour="*/4"),
    },
    "update_inventory_price_quantity-30min": {
        "task": "inventoryApp.tasks.update_inventory_price_quantity_task",
        "schedule": crontab(minute="*/30"),
    },
    "check-marketplace-item-ended-8-hours": {
        "task": "inventoryApp.tasks.check_product_ended_status_task",
        "schedule": crontab(hour="*/8"),
    },
    # "map-marketplace-items-to-vendor-4hr": {
    #     "task": "inventoryApp.tasks.map_marketplace_items_to_vendor_task",
    #     "schedule": crontab(minute="*/5"),
    # },
}


@task_prerun.connect
def close_db_connections(**kwargs):
    db.connections.close_all()
