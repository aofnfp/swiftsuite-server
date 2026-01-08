from celery import shared_task
from django.core.cache import cache
from .utils import download_marketplace_items_to_inventory, map_marketplace_items_to_vendor
from .update_market import check_ended_status_update_quantity_price, update_inventory_price_quantity


@shared_task(queue='heavy-inv', bind=True)
def download_marketplace_items_to_inventory_task(self):
    if not cache.add("download_marketplace_items_to_inventory_task", "1", timeout=7200):
        return "download_marketplace_items_to_inventory_task already running"
    try:
        """Background task to sync eBay items with local database"""
        download_marketplace_items_to_inventory()
        return "Download marketplace items to inventory completed successfully"
    finally:
        cache.delete("download_marketplace_items_to_inventory_task")

@shared_task(queue='default', bind=True)
def update_inventory_price_quantity_task(self):
    if not cache.add("update_inventory_price_quantity_task", "1", timeout=7200):
        return "update_inventory_price_quantity_task already running"
    try:
        """Background task to sync inventory price and quantity with local database"""
        update_inventory_price_quantity()
        return "Quantity and price update completed successfully"
    finally:
        cache.delete("update_inventory_price_quantity_task")

@shared_task(queue='default', bind=True)
def check_ended_status_update_quantity_price_task(self):
    if not cache.add("check_ended_status_update_quantity_price_task", "1", timeout=7200):
        return "check_ended_status_update_quantity_price_task already running"
    try:
        """Background task to check if eBay items have ended"""
        check_ended_status_update_quantity_price()
        return "Check eBay item ended completed successfully"
    finally:
        cache.delete("check_ended_status_update_quantity_price_task")

@shared_task(queue='default', bind=True)
def map_marketplace_items_to_vendor_task(self):
    if not cache.add("map_marketplace_items_to_vendor_task", "1", timeout=7200):
        return "map_marketplace_items_to_vendor_task already running"
    try:
        """Background task to map marketplace items to vendor update tables"""
        map_marketplace_items_to_vendor()
        return "Mapping marketplace items to vendor completed successfully"
    finally:
        cache.delete("map_marketplace_items_to_vendor_task")