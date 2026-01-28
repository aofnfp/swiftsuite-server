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
from django.utils import timezone
from marketplaceApp.views import Ebay


LOCK_TIMEOUT = 60 * 120  # 2 hours

LOCK_KEY = "download_update_marketplace_items_task_lock"
@shared_task(queue='heavy-inv')
def download_item_update_market_price_quantity_task():
    if not cache.add(LOCK_KEY, "1", timeout=LOCK_TIMEOUT):
        logger.info("download_item_update_market_price_quantity_task skipped: already running")
        return "Skipped (already running)"

    logger.info("download_item_update_market_price_quantity_task started")

    try:
        download_item_update_market_price_quantity()
        logger.info("download_item_update_market_price_quantity_task completed successfully")
        return "Completed successfully"
    finally:
        cache.delete(LOCK_KEY)



LOCK_KEY2 = "update_inventory_price_quantity_task_lock"
@shared_task(queue='default')
def update_inventory_price_quantity_task():
    if not cache.add(LOCK_KEY2, "1", timeout=LOCK_TIMEOUT):
        logger.info("update_inventory_price_quantity_task skipped: already running")
        return "Skipped (already running)"

    logger.info("update_inventory_price_quantity_task started")

    try:
        update_inventory_price_quantity()
        logger.info("update_inventory_price_quantity_task completed successfully")
        return "Completed successfully"
    finally:
        cache.delete(LOCK_KEY2)



LOCK_KEY3 = "check_product_ended_status_task_lock"
@shared_task(queue='default')
def check_product_ended_status_task():
    if not cache.add(LOCK_KEY3, "1", timeout=LOCK_TIMEOUT):
        logger.info("check_product_ended_status_task skipped: already running")
        return "Skipped (already running)"

    logger.info("check_product_ended_status_task started")

    try:
        check_product_ended_status()
        logger.info("check_product_ended_status_task completed successfully")
        return "Completed successfully"
    finally:
        cache.delete(LOCK_KEY3)



LOCK_KEY4 = "map_marketplace_items_to_vendor_task_lock"
@shared_task(queue='default')
def map_marketplace_items_to_vendor_task():
    if not cache.add(LOCK_KEY4, "1", timeout=LOCK_TIMEOUT):
        logger.info("map_marketplace_items_to_vendor_task skipped: already running")
        return "Skipped (already running)"

    logger.info("map_marketplace_items_to_vendor_task started")

    try:
        map_marketplace_items_to_vendor()
        logger.info("map_marketplace_items_to_vendor_task completed successfully")
        return "Completed successfully"
    finally:
        cache.delete(LOCK_KEY4)
