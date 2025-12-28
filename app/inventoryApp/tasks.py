from celery import shared_task
from .utils import sync_ebay_items_with_local
from .update_market import check_ended_status_update_quantity_price, update_inventory_price_quantity


@shared_task(queue='heavy-inv')
def sync_ebay_inventory_task():
    """Background task to sync eBay items with local database"""
    sync_ebay_items_with_local()
    return "Inventory Sync completed successfully"

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