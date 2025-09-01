from celery import shared_task
from inventoryApp import sync_ebay_items_with_local

@shared_task
def sync_ebay_inventory_task():
    """Background task to sync eBay items with local database"""
    sync_ebay_items_with_local()
    return "Sync completed successfully"
