from celery import shared_task
from django.core.cache import cache
from .utils import download_item_update_market_price_quantity, map_marketplace_items_to_vendor
from .update_market import check_product_ended_status, update_inventory_price_quantity
import logging
logger = logging.getLogger(__name__)
from celery.exceptions import Ignore


LOCK_KEY = "download_update_marketplace_items_task_lock"
LOCK_TIMEOUT = 7200
@shared_task(queue='heavy-inv', bind=True)
def download_update_marketplace_items_task(self):
    if not cache.add(LOCK_KEY, "1", timeout=LOCK_TIMEOUT):
        logger.info("download_update_marketplace_items_task skipped: already running")
        raise Ignore() 

    logger.info("download_update_marketplace_items_task started")
    try:
        """Background task to sync eBay items with local database"""
        download_item_update_market_price_quantity()
        logger.info("download_update_marketplace_items_task completed successfully")
    finally:
        cache.delete(LOCK_KEY)


LOCK_KEY2 = "update_inventory_price_quantity_task_lock"
@shared_task(queue='default', bind=True)
def update_inventory_price_quantity_task(self):
    if not cache.add(LOCK_KEY2, "1", timeout=LOCK_TIMEOUT):
        logger.info("update_inventory_price_quantity_task skipped: already running")
        raise Ignore() 

    logger.info("update_inventory_price_quantity_task started")
    try:
        """Background task to sync inventory price and quantity with local database"""
        update_inventory_price_quantity()
        logger.info("Quantity and price update completed successfully")
    finally:
        cache.delete(LOCK_KEY2)


LOCK_KEY3 = "check_product_ended_status_task_lock"
@shared_task(queue='default', bind=True)
def check_product_ended_status_task(self):
    if not cache.add(LOCK_KEY3, "1", timeout=7200):
        logger.info("check_product_ended_status_task skipped: already running")
        raise Ignore()
    try:
        """Background task to check if eBay items have ended"""
        check_product_ended_status()
        logger.info("Check eBay item ended completed successfully")
    finally:
        cache.delete(LOCK_KEY3)


# LOCK_KEY4 = "map_marketplace_items_to_vendor_task_lock"
@shared_task(queue='default')
def map_marketplace_items_to_vendor_task():
    # if not cache.add(LOCK_KEY4, "1", timeout=7200):
    #     logger.info("map_marketplace_items_to_vendor_task skipped: already running")
    #     raise Ignore()
    """Mapping marketplace items to vendor started"""
    map_marketplace_items_to_vendor()
    return "Mapping marketplace items to vendor completed successfully"
    # try:
    #     """Background task to map marketplace items to vendor update tables"""
    #     map_marketplace_items_to_vendor()
    #     logger.info("Mapping marketplace items to vendor completed successfully")
    # finally:
    #     cache.delete(LOCK_KEY4)