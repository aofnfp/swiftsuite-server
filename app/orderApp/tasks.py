from celery import shared_task
from .utils import sync_ebay_order_with_local


@shared_task(queue='default')
def sync_ebay_order_task():
    """Background task to sync eBay items with local database"""
    sync_ebay_order_with_local()
    return "Order Sync completed successfully"
