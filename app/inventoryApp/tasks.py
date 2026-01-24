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
        "X-EBAY-API-SITEID": "0",
        "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
        "Content-Type": "text/xml",
    }
    
    while True:
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
          <DetailLevel>ReturnAll</DetailLevel>
        </GetSellerListRequest>
        """
        
        try:
            response = requests.post(EBAY_URL, headers=HEADERS, data=body, timeout=30)
            response.raise_for_status()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for page {page}: {e}")
            break
        
        try:
            root = ET.fromstring(response.text)
            
            # Check for API errors
            ack = root.findtext(".//e:Ack", default=None, namespaces=NAMESPACE)
            if ack == "Failure":
                error_message = root.findtext(".//e:Errors/e:LongMessage", default="Unknown error", namespaces=NAMESPACE)
                logger.error(f"eBay API error: {error_message}")
                break
                
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML response: {e}")
            break
        
        page_items = root.findall(".//e:Item", NAMESPACE)
        if not page_items:
            break
        
        for item in page_items:
            items.append({
                "ebay_item_id": item.findtext("e:ItemID", default="Not Found", namespaces=NAMESPACE),
                "ebay_sku": item.findtext("e:SKU", default="N/A", namespaces=NAMESPACE),
                "Title": item.findtext("e:Title", default="No Title", namespaces=NAMESPACE),
                "ebay_price": item.findtext("e:SellingStatus/e:CurrentPrice", default="0", namespaces=NAMESPACE),
                "ebay_quantity": item.findtext("e:Quantity", default="0", namespaces=NAMESPACE),
                "quantity_sold": item.findtext("e:SellingStatus/e:QuantitySold", default="0", namespaces=NAMESPACE),
                "ListingDuration": item.findtext("e:ListingDuration", default="N/A", namespaces=NAMESPACE),
                "ListingType": item.findtext("e:ListingType", default="N/A", namespaces=NAMESPACE),
                "PictureDetails": item.findtext("e:PictureDetails/e:GalleryURL", default="N/A", namespaces=NAMESPACE),
                "ShippingProfileID": item.findtext("e:SellerProfiles/e:SellerShippingProfile/e:ShippingProfileID", default="N/A", namespaces=NAMESPACE),
                "ShippingProfileName": item.findtext("e:SellerProfiles/e:SellerShippingProfile/e:ShippingProfileName", default="N/A", namespaces=NAMESPACE),
                "ReturnProfileID": item.findtext("e:SellerProfiles/e:SellerReturnProfile/e:ReturnProfileID", default="N/A", namespaces=NAMESPACE),
                "ReturnProfileName": item.findtext("e:SellerProfiles/e:SellerReturnProfile/e:ReturnProfileName", default="N/A", namespaces=NAMESPACE),
                "PaymentProfileID": item.findtext("e:SellerProfiles/e:SellerPaymentProfile/e:PaymentProfileID", default="N/A", namespaces=NAMESPACE),
                "PaymentProfileName": item.findtext("e:SellerProfiles/e:SellerPaymentProfile/e:PaymentProfileName", default="N/A", namespaces=NAMESPACE),
                "market_item_url": item.findtext(".//e:ViewItemURL", default="N/A", namespaces=NAMESPACE),
            })
        
        # Check if there are more pages
        total_pages = root.findtext(".//e:PaginationResult/e:TotalNumberOfPages", default="1", namespaces=NAMESPACE)
        if page >= int(total_pages):
            break
            
        page += 1
        time.sleep(0.5)  # REQUIRED throttling
    
    return items


def _extract_product_details(product_details, item):
    """
    Extract and process product details from eBay API response.
    
    Args:
        product_details (dict): Product details from get_item_details
        item (dict): Item data from _fetch_window
    
    Returns:
        tuple: (ebay_upc, ebay_mpn, custom_fields)
    """
    ebay_upc = ""
    ebay_mpn = ""
    custom_fields = {}
    
    if not product_details:
        return ebay_upc, ebay_mpn, custom_fields
    
    # Extract UPC and MPN
    localized_aspects = product_details.get("localizedAspects", [])
    for aspect in localized_aspects:
        name = aspect.get("name", "")
        value = aspect.get("value", "")
        
        if name and value:
            custom_fields[name] = value
            
            if name.upper() == "UPC":
                ebay_upc = value
            elif name.upper() == "MPN":
                ebay_mpn = value
    
    # Fallback to product_details MPN if not found in localized aspects
    if not ebay_mpn and product_details.get("mpn"):
        ebay_mpn = product_details.get("mpn")
    
    return ebay_upc, ebay_mpn, custom_fields


def _create_inventory_defaults(product_details, item, user, ebay_upc, ebay_mpn, custom_fields):
    """
    Create defaults dictionary for InventoryModel update_or_create.
    
    Args:
        product_details (dict): Product details
        item (dict): Item data
        user: User object
        ebay_upc (str): UPC value
        ebay_mpn (str): MPN value
        custom_fields (dict): Custom fields
    
    Returns:
        dict: Defaults dictionary for InventoryModel
    """
    # Handle item location safely
    item_location = product_details.get("itemLocation", {})
    
    # Handle price safely
    price_info = product_details.get("price", {})
    price_value = price_info.get("value", "0") if price_info else "0"
    
    # Handle images safely
    image_info = product_details.get("image", {})
    image_url = image_info.get("imageUrl", "") if image_info else ""
    
    # Handle date safely
    creation_date = product_details.get("itemCreationDate", "")
    date_created = creation_date.split("T")[0] if creation_date else ""
    
    defaults = {
        "title": item.get("Title", ""),
        "description": json.dumps(product_details.get("shortDescription", "")),
        "location": item_location.get("country", ""),
        "category_id": product_details.get("categoryId", ""),
        "category": product_details.get("categoryPath", ""),
        "sku": item.get("ebay_sku", ""),
        "upc": ebay_upc,
        "mpn": ebay_mpn,
        "start_price": price_value,
        "price": price_value,
        "cost": price_value,
        "picture_detail": image_url,
        "thumbnailImage": product_details.get("additionalImages", []),
        "postal_code": item_location.get("postalCode", ""),
        "city": item_location.get("city", ""),
        "country": item_location.get("country", ""),
        "quantity": item.get("ebay_quantity", "0"),
        "return_profileID": item.get("ReturnProfileID", ""),
        "return_profileName": item.get("ReturnProfileName", ""),
        "payment_profileID": item.get("PaymentProfileID", ""),
        "payment_profileName": item.get("PaymentProfileName", ""),
        "shipping_profileID": item.get("ShippingProfileID", ""),
        "shipping_profileName": item.get("ShippingProfileName", ""),
        "bestOfferEnabled": True,
        "listingType": item.get("ListingType", ""),
        "item_specific_fields": custom_fields,
        "market_logos": product_details.get("listingMarketplaceId", ""),
        "date_created": date_created,
        "active": True,
        "vendor_name": "Not Found",
        "map_status": False,
        "market_name": "Ebay",
        "fixed_percentage_markup": user.fixed_percentage_markup,
        "fixed_markup": user.fixed_markup,
        "profit_margin": user.profit_margin,
        "min_profit_mergin": user.min_profit_mergin,
        "charity_id": user.charity_id,
        "enable_charity": user.enable_charity,
        "market_item_url": item.get("market_item_url", ""),
        "last_updated": timezone.now(),
    }
    
    return defaults


@shared_task(
    queue='heavy-inv',
    bind=True,
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3, "countdown": 30},
    rate_limit="6/m"
)
def download_item_update_market_price_quantity(self, months_back=12):
    """
    Celery task to download and update eBay inventory items.
    
    Args:
        self: Celery task instance
        months_back (int): Number of months to look back (default: 12)
    """
    user_tokens = MarketplaceEnronment.objects.all()
    eb = Ebay()
    for user in user_tokens:
        if user.marketplace_name != "Ebay":
            continue

        access_token = eb.refresh_access_token(user.user_id, "Ebay")
        try:
            end = datetime.utcnow()
            total_processed = 0
            windows_processed = 0
            
            # Process in 7-day windows
            for window_num in range(months_back * 4):  # 4 windows per month
                start = end - timedelta(days=7)
                
                # Log window being processed
                logger.info(f"Processing window {window_num + 1}: {start.isoformat()} to {end.isoformat()}")
                
                window_items = _fetch_window(
                    access_token, 
                    start.isoformat(), 
                    end.isoformat()
                )
                
                if not window_items:
                    logger.info(f"No items found in window {window_num + 1}")
                    break
                
                logger.info(f"Found {len(window_items)} items in window {window_num + 1}")
                
                for item in window_items:
                    try:
                        # Try to get existing item
                        existing_item = InventoryModel.objects.get(
                            user_id=user.user_id, 
                            market_item_id=item["ebay_item_id"]
                        )
                        
                        # Update basic info
                        InventoryModel.objects.filter(
                            user_id=user.user_id, 
                            market_item_id=item["ebay_item_id"]
                        ).update(
                            market_item_url=item["market_item_url"],
                            last_updated=timezone.now()
                        )
                        
                        # Check if price or quantity changed
                        price_changed = (existing_item.start_price != item["ebay_price"])
                        quantity_changed = (existing_item.quantity != item["ebay_quantity"])
                        
                        if price_changed or quantity_changed:
                            # Assuming update_items_quantity_or_price_on_ebay is defined elsewhere
                            update_items_quantity_or_price_on_ebay(
                                user.user_id,
                                item["ebay_item_id"],
                                existing_item.start_price,
                                existing_item.quantity,
                                user._id  # Note: Consider using user.id instead
                            )
                            
                    except InventoryModel.DoesNotExist:
                        # Item doesn't exist, create new entry
                        try:
                            # Assuming get_item_details is defined elsewhere
                            product_details = get_item_details(user._id, item["ebay_item_id"])
                            if not product_details:
                                logger.warning(f"No product details for item {item['ebay_item_id']}")
                                continue
                            
                            # Extract product details
                            ebay_upc, ebay_mpn, custom_fields = _extract_product_details(
                                product_details, 
                                item
                            )
                            
                            # Create defaults dictionary
                            defaults = _create_inventory_defaults(
                                product_details, 
                                item, 
                                user, 
                                ebay_upc, 
                                ebay_mpn, 
                                custom_fields
                            )
                            
                            # Create or update inventory item
                            inventory, created = InventoryModel.objects.update_or_create(
                                user_id=user.user_id,
                                market_item_id=item.get("ebay_item_id"),
                                defaults=defaults
                            )
                            
                            if created:
                                logger.info(f"Created new inventory item: {item['ebay_item_id']}")
                            else:
                                logger.info(f"Updated existing inventory item: {item['ebay_item_id']}")
                                
                        except Exception as e:
                            logger.exception(f"Failed to process new item {item['ebay_item_id']}: {e}")
                            continue
                    
                    total_processed += 1
                    
                    # Update progress periodically
                    if total_processed % 10 == 0:
                        self.update_state(
                            state="PROGRESS",
                            meta={
                                "items_processed": total_processed,
                                "windows_processed": windows_processed,
                                "current_user": user.user_id
                            }
                        )
                
                # Move to previous window
                end = start
                windows_processed += 1
                time.sleep(1)  # Window throttle
                
                # Update progress after each window
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "items_processed": total_processed,
                        "windows_processed": windows_processed,
                        "current_user": user.user_id
                    }
                )
            
            # Final progress update for this user
            self.update_state(
                state="PROGRESS",
                meta={
                    "items_processed": total_processed,
                    "windows_processed": windows_processed,
                    "current_user": user.user_id,
                    "status": f"Completed processing for user {user.user_id}"
                }
            )
            
            logger.info(f"Completed processing for user {user.user_id}: {total_processed} items")
            
        except Exception as e:
            logger.exception(f"eBay inventory sync failed for user {user.user_id}: {e}")
            continue
    
    return {
        "status": "COMPLETED",
        "message": f"Processed {len(user_tokens)} users"
    }
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
