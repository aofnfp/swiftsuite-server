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



def _fetch_window(access_token, start_time, end_time):
    """
    Fetch eBay items within a specific time window.
    
    Args:
        access_token (str): eBay API access token
        start_time (str): Start time in ISO format
        end_time (str): End time in ISO format
    
    Returns:
        list: List of item dictionaries
    """
    items = []
    page = 1
    EBAY_URL = "https://api.ebay.com/ws/api.dll"
    
    NAMESPACE = {"e": "urn:ebay:apis:eBLBaseComponents"}
    
    HEADERS = {
        "X-EBAY-API-CALL-NAME": "GetSellerList",
        "X-EBAY-API-SITEID": "0",  # US site - verify this is correct for your case
        "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
        "Content-Type": "text/xml",
        "X-EBAY-API-IAF-TOKEN": access_token,  # Alternative auth method
    }
    
    while True:
        # IMPORTANT: Use proper XML escaping for the access token
        # The access token might contain special characters that break XML
        import html
        escaped_token = html.escape(access_token)
        
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                <GetSellerListRequest xmlns="urn:ebay:apis:eBLBaseComponents">
                    <RequesterCredentials>
                        <eBayAuthToken>{escaped_token}</eBayAuthToken>
                    </RequesterCredentials>
                    <StartTimeFrom>{start_time}</StartTimeFrom>
                    <StartTimeTo>{end_time}</StartTimeTo>
                    <Pagination>
                        <EntriesPerPage>50</EntriesPerPage>
                        <PageNumber>{page}</PageNumber>
                    </Pagination>
                    <DetailLevel>ReturnAll</DetailLevel>
                    <GranularityLevel>Coarse</GranularityLevel>  <!-- Add this to reduce data size -->
                    <OutputSelector>ItemID</OutputSelector>
                    <OutputSelector>SKU</OutputSelector>
                    <OutputSelector>Title</OutputSelector>
                    <OutputSelector>SellingStatus</OutputSelector>
                    <OutputSelector>Quantity</OutputSelector>
                    <OutputSelector>ListingDuration</OutputSelector>
                    <OutputSelector>ListingType</OutputSelector>
                    <OutputSelector>PictureDetails</OutputSelector>
                    <OutputSelector>SellerProfiles</OutputSelector>
                    <OutputSelector>ViewItemURL</OutputSelector>
                </GetSellerListRequest>"""
        
        try:
            # Add timeout and verify=False only if needed (for development)
            response = requests.post(
                EBAY_URL, 
                headers=HEADERS, 
                data=body.encode('utf-8'),  # Explicit encoding
                timeout=60,
                verify=True  # Set to False only for debugging with SSL issues
            )
            
            # Log raw response for debugging
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                # Try to get more detailed error info
                error_content = response.text[:500]  # First 500 chars
                logger.error(f"HTTP Error {response.status_code}: {error_content}")
                break
                
            # Try to parse with error recovery
            try:
                # Use XMLParser with recovery for malformed XML
                parser = ET.XMLParser(recover=True)
                root = ET.fromstring(response.text, parser=parser)
            except ET.ParseError as parse_error:
                # Try to extract error message from malformed XML
                logger.error(f"XML Parse Error: {parse_error}")
                logger.error(f"Problematic XML start: {response.text[:500]}")
                
               
            # Check if there are more pages
            total_pages_elem = root.find(".//{urn:ebay:apis:eBLBaseComponents}PaginationResult/{urn:ebay:apis:eBLBaseComponents}TotalNumberOfPages")
            if total_pages_elem is not None and total_pages_elem.text:
                total_pages = int(total_pages_elem.text)
                if page >= total_pages:
                    logger.info(f"Reached last page ({page}/{total_pages})")
                    break
            
            page += 1
            
            # Rate limiting - be more conservative
            if page % 10 == 0:
                logger.info(f"Processed {page} pages, sleeping...")
                time.sleep(2)
            else:
                time.sleep(1)
            
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout on page {page}")
            break
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error on page {page}")
            break
        except Exception as e:
            logger.exception(f"Unexpected error on page {page}: {e}")
            break
    
    logger.info(f"Total items fetched: {len(items)}")
    # return items


@shared_task(
    queue='heavy-inv',
    bind=True,
    autoretry_for=(requests.exceptions.RequestException, ET.ParseError),
    retry_kwargs={"max_retries": 3, "countdown": 60},  # Longer retry delay
    rate_limit="4/m"  # More conservative rate limit
)
def download_item_update_market_price_quantity(self, months_back=12):
    """
    Celery task to download and update eBay inventory items.
    """
    from django.db import transaction
    eb = Ebay()
    user_tokens = MarketplaceEnronment.objects.filter(marketplace_name="Ebay")
        """
    Fetch eBay items within a specific time window.
    
    Args:
        access_token (str): eBay API access token
        start_time (str): Start time in ISO format
        end_time (str): End time in ISO format
    
    Returns:
        list: List of item dictionaries
    """
    items = []
    page = 1
    EBAY_URL = "https://api.ebay.com/ws/api.dll"
    
    NAMESPACE = {"e": "urn:ebay:apis:eBLBaseComponents"}
    
    HEADERS = {
        "X-EBAY-API-CALL-NAME": "GetSellerList",
        "X-EBAY-API-SITEID": "0",  # US site - verify this is correct for your case
        "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
        "Content-Type": "text/xml",
        "X-EBAY-API-IAF-TOKEN": access_token,  # Alternative auth method
    }
    
    while True:
        # IMPORTANT: Use proper XML escaping for the access token
        # The access token might contain special characters that break XML
        import html
        escaped_token = html.escape(access_token)
        
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                <GetSellerListRequest xmlns="urn:ebay:apis:eBLBaseComponents">
                    <RequesterCredentials>
                        <eBayAuthToken>{escaped_token}</eBayAuthToken>
                    </RequesterCredentials>
                    <StartTimeFrom>{start_time}</StartTimeFrom>
                    <StartTimeTo>{end_time}</StartTimeTo>
                    <Pagination>
                        <EntriesPerPage>50</EntriesPerPage>
                        <PageNumber>{page}</PageNumber>
                    </Pagination>
                    <DetailLevel>ReturnAll</DetailLevel>
                    <GranularityLevel>Coarse</GranularityLevel>  <!-- Add this to reduce data size -->
                    <OutputSelector>ItemID</OutputSelector>
                    <OutputSelector>SKU</OutputSelector>
                    <OutputSelector>Title</OutputSelector>
                    <OutputSelector>SellingStatus</OutputSelector>
                    <OutputSelector>Quantity</OutputSelector>
                    <OutputSelector>ListingDuration</OutputSelector>
                    <OutputSelector>ListingType</OutputSelector>
                    <OutputSelector>PictureDetails</OutputSelector>
                    <OutputSelector>SellerProfiles</OutputSelector>
                    <OutputSelector>ViewItemURL</OutputSelector>
                </GetSellerListRequest>"""
        
        try:
            # Add timeout and verify=False only if needed (for development)
            response = requests.post(
                EBAY_URL, 
                headers=HEADERS, 
                data=body.encode('utf-8'),  # Explicit encoding
                timeout=60,
                verify=True  # Set to False only for debugging with SSL issues
            )
            
            # Log raw response for debugging
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                # Try to get more detailed error info
                error_content = response.text[:500]  # First 500 chars
                logger.error(f"HTTP Error {response.status_code}: {error_content}")
                break
                
            # Try to parse with error recovery
            try:
                # Use XMLParser with recovery for malformed XML
                parser = ET.XMLParser(recover=True)
                root = ET.fromstring(response.text, parser=parser)
            except ET.ParseError as parse_error:
                # Try to extract error message from malformed XML
                logger.error(f"XML Parse Error: {parse_error}")
                logger.error(f"Problematic XML start: {response.text[:500]}")
                
               
            # Check if there are more pages
            total_pages_elem = root.find(".//{urn:ebay:apis:eBLBaseComponents}PaginationResult/{urn:ebay:apis:eBLBaseComponents}TotalNumberOfPages")
            if total_pages_elem is not None and total_pages_elem.text:
                total_pages = int(total_pages_elem.text)
                if page >= total_pages:
                    logger.info(f"Reached last page ({page}/{total_pages})")
                    break
            
            page += 1
            
            # Rate limiting - be more conservative
            if page % 10 == 0:
                logger.info(f"Processed {page} pages, sleeping...")
                time.sleep(2)
            else:
                time.sleep(1)
            
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout on page {page}")
            break
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error on page {page}")
            break
        except Exception as e:
            logger.exception(f"Unexpected error on page {page}: {e}")
            break
    
    logger.info(f"Total items fetched: {len(items)}")
    


# @shared_task(
#     bind=True,
#     autoretry_for=(requests.exceptions.RequestException,),
#     retry_kwargs={"max_retries": 3, "countdown": 30},
#     rate_limit="6/m"
# )
# def fetch_all_ebay_items_task(self, access_token, months_back=12):
#     """
#     Celery-safe task to fetch ALL seller listings without 504s
#     """

#     all_items = []
#     end = datetime.utcnow()

#     for _ in range(months_back * 4):  # 7-day windows
#         start = end - timedelta(days=7)

#         window_items = _fetch_window(
#             access_token,
#             start.isoformat(),
#             end.isoformat()
#         )

#         if not window_items:
#             break

#         all_items.extend(window_items)
#         end = start

#         # Optional: progress reporting
#         self.update_state(
#             state="PROGRESS",
#             meta={"items_fetched": len(all_items)}
#         )

#     return {
#         "total_items": len(all_items),
#         "items": all_items
#     }
