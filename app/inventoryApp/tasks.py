# inventoryapp/tasks.py
from celery import shared_task
from .views import MarketInventory

@shared_task
def sync_ebay_inventory_task():
    """Background task to sync eBay items with local database"""
    MarketInventory.sync_ebay_items_with_local()
    return "Sync completed successfully"
