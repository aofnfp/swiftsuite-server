from celery import shared_task
from .utils import sync_ebay_items_with_local
from .update_market import check_and_update_ended_ebay_items, update_ebay_price_quantity


@shared_task(queue='heavy-cpu')
def sync_ebay_inventory_task():
    """Background task to sync eBay items with local database"""
    sync_ebay_items_with_local()
    return "Inventory Sync completed successfully"

@shared_task(queue='default')
def update_ebay_price_quantity_inventory_task():
    """Background task to sync eBay items price and quantity with local database"""
    update_ebay_price_quantity()
    return "Quantity and price update completed successfully"

@shared_task(queue='default')
def check_ebay_item_ended_task():
    """Background task to check if eBay items have ended"""
    check_and_update_ended_ebay_items()
    return "Check eBay item ended completed successfully"