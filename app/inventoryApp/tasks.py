from celery import shared_task
from django.core.cache import cache
from .utils import download_marketplace_items_to_inventory, map_marketplace_items_to_vendor
from .update_market import check_ended_status_update_quantity_price, update_inventory_price_quantity
import logging
logger = logging.getLogger(__name__)
from celery.exceptions import Ignore


LOCK_KEY = "download_marketplace_items_to_inventory_task_lock"
LOCK_TIMEOUT = 7200
@shared_task(queue='heavy-inv', bind=True)
def download_marketplace_items_to_inventory_task(self):
    if not cache.add(LOCK_KEY, "1", timeout=LOCK_TIMEOUT):
        logger.info("download_marketplace_items_to_inventory_task skipped: already running")
        raise Ignore() 

    logger.info("download_marketplace_items_to_inventory_task started")
    try:
        """Background task to sync eBay items with local database"""
        download_marketplace_items_to_inventory()
        logger.info("download_marketplace_items_to_inventory_task completed successfully")
    finally:
        cache.delete(LOCK_KEY)


LOCK_KEY = "update_inventory_price_quantity_task_lock"
@shared_task(queue='default', bind=True)
def update_inventory_price_quantity_task(self):
    if not cache.add(LOCK_KEY, "1", timeout=LOCK_TIMEOUT):
        logger.info("update_inventory_price_quantity_task skipped: already running")
        raise Ignore() 

    logger.info("update_inventory_price_quantity_task started")
    try:
        """Background task to sync inventory price and quantity with local database"""
        update_inventory_price_quantity()
        logger.info("Quantity and price update completed successfully")
    finally:
        cache.delete(LOCK_KEY)


LOCK_KEY = "check_ended_status_update_quantity_price_task_lock"
@shared_task(queue='default', bind=True)
def check_ended_status_update_quantity_price_task(self):
    if not cache.add(LOCK_KEY, "1", timeout=7200):
        logger.info("check_ended_status_update_quantity_price_task skipped: already running")
        raise Ignore()
    try:
        """Background task to check if eBay items have ended"""
        check_ended_status_update_quantity_price()
        logger.info("Check eBay item ended completed successfully")
    finally:
        cache.delete(LOCK_KEY)


LOCK_KEY = "map_marketplace_items_to_vendor_task_lock"
@shared_task(queue='default', bind=True)
def map_marketplace_items_to_vendor_task(self):
    if not cache.add(LOCK_KEY, "1", timeout=7200):
        logger.info("map_marketplace_items_to_vendor_task skipped: already running")
        raise Ignore()
    try:
        """Background task to map marketplace items to vendor update tables"""
        map_marketplace_items_to_vendor()
        logger.info("Mapping marketplace items to vendor completed successfully")
    finally:
        cache.delete(LOCK_KEY)