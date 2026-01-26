from celery import shared_task
from django.core.cache import cache
from .utils import download_item_update_market_price_quantity, map_marketplace_items_to_vendor
from .update_market import check_product_ended_status, update_inventory_price_quantity
import logging
logger = logging.getLogger(__name__)
from celery.exceptions import Ignore

import time
import requests
import xml.etree.ElementTree as ET
from celery import shared_task
from datetime import datetime, timedelta
import json
from .models import InventoryModel, UpdateLogModel
from marketplaceApp.models import MarketplaceEnronment
from .utils import get_item_details, update_items_quantity_or_price_on_ebay
from django.utils import timezone
from marketplaceApp.views import Ebay


# LOCK_KEY = "download_update_marketplace_items_task_lock"
@shared_task(queue='heavy-inv')
def download_item_update_market_price_quantity_task():
    """Background task to sync eBay items with local database and update price and quantity"""
    download_item_update_market_price_quantity()
    logger.info("download_item_update_market_price_quantity_task completed successfully")


@shared_task(queue='default')
def update_inventory_price_quantity_task():
    """Background task to sync inventory price and quantity with local database"""
    update_inventory_price_quantity()
    logger.info("update_inventory_price_quantity_task completed successfully")
  

LOCK_KEY3 = "check_product_ended_status_task_lock"
@shared_task(queue='default', bind=True)
def check_product_ended_status_task(self):
    if not cache.add(LOCK_KEY3, "1", timeout=7200):
        logger.info("check_product_ended_status_task skipped: already running")
        raise Ignore()
    
    logger.info("check_product_ended_status_task started")
    try:
        """Background task to check if eBay items have ended"""
        check_product_ended_status()
        logger.info("Check eBay item ended completed successfully")
    finally:
        cache.delete(LOCK_KEY3)


@shared_task(queue='default')
def map_marketplace_items_to_vendor_task():
    """Background task to map marketplace items to vendor update tables"""
    map_marketplace_items_to_vendor()
    logger.info("map_marketplace_items_to_vendor_task completed successfully")


