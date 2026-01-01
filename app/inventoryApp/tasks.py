from celery import shared_task
from .utils import download_marketplace_items_to_inventory, map_marketplace_items_to_vendor
from .update_market import check_ended_status_update_quantity_price, update_inventory_price_quantity


@shared_task(queue='heavy-inv')
def download_marketplace_items_to_inventory_task():
    """Background task to sync eBay items with local database"""
    download_marketplace_items_to_inventory()
    return "Download marketplace items to inventory completed successfully"

@shared_task(queue='default')
def update_inventory_price_quantity_task():
    """Background task to sync inventory price and quantity with local database"""
    update_inventory_price_quantity()
    return "Quantity and price update completed successfully"

@shared_task(queue='default')
def check_ended_status_update_quantity_price_task():
    """Background task to check if eBay items have ended"""
    check_ended_status_update_quantity_price()
    return "Check eBay item ended completed successfully"

@shared_task(queue='default')
def map_marketplace_items_to_vendor_task():
    """Background task to map marketplace items to vendor update tables"""
    map_marketplace_items_to_vendor()
    return "Mapping marketplace items to vendor completed successfully"

