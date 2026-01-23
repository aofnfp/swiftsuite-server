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




EBAY_URL = "https://api.ebay.com/ws/api.dll"
NAMESPACE = {'e': 'urn:ebay:apis:eBLBaseComponents'}

HEADERS = {
    "X-EBAY-API-CALL-NAME": "GetSellerList",
    "X-EBAY-API-SITEID": "0",
    "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
    "Content-Type": "text/xml"
}


def _fetch_window(access_token, start_time, end_time):
    """
    Fetch one 7-day window safely
    """
    items = []
    page = 1
    MAX_PAGES = 20

    while page <= MAX_PAGES:
        body = f"""<?xml version="1.0" encoding="utf-8"?>
        <GetSellerListRequest xmlns="urn:ebay:apis:eBLBaseComponents">
          <RequesterCredentials>
            <eBayAuthToken>{access_token}</eBayAuthToken>
          </RequesterCredentials>

          <StartTimeFrom>{start_time}</StartTimeFrom>
          <StartTimeTo>{end_time}</StartTimeTo>

          <Pagination>
            <EntriesPerPage>50</EntriesPerPage>
            <PageNumber>{page}</PageNumber>
          </Pagination>

          <DetailLevel>ReturnSummary</DetailLevel>
        </GetSellerListRequest>
        """

        response = requests.post(
            EBAY_URL,
            headers=HEADERS,
            data=body,
            timeout=20
        )

        if response.status_code != 200:
            break

        root = ET.fromstring(response.text)
        page_items = root.findall(".//e:Item", NAMESPACE)

        if not page_items:
            break

        for item in page_items:
            items.append({
                "item_id": item.findtext("e:ItemID", default="", namespaces=NAMESPACE),
                "sku": item.findtext("e:SKU", default="", namespaces=NAMESPACE),
                "title": item.findtext("e:Title", default="", namespaces=NAMESPACE),
                "price": item.findtext(
                    "e:SellingStatus/e:CurrentPrice",
                    default="",
                    namespaces=NAMESPACE
                ),
            })

        page += 1
        time.sleep(0.4)  # throttle (critical)

    return items


@shared_task(
    bind=True,
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3, "countdown": 30},
    rate_limit="6/m"
)
def fetch_all_ebay_items_task(self, access_token, months_back=12):
    """
    Celery-safe task to fetch ALL seller listings without 504s
    """

    all_items = []
    end = datetime.utcnow()

    for _ in range(months_back * 4):  # 7-day windows
        start = end - timedelta(days=7)

        window_items = _fetch_window(
            access_token,
            start.isoformat(),
            end.isoformat()
        )

        if not window_items:
            break

        all_items.extend(window_items)
        end = start

        # Optional: progress reporting
        self.update_state(
            state="PROGRESS",
            meta={"items_fetched": len(all_items)}
        )

    return {
        "total_items": len(all_items),
        "items": all_items
    }
