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
            
            # Check if response is valid XML
            if not response.text.strip().startswith('<?xml'):
                logger.error(f"Non-XML response received: {response.text[:200]}")
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
                
                # Try to find error in response text
                import re
                error_match = re.search(r'error.*?message="([^"]+)"', response.text, re.IGNORECASE)
                if error_match:
                    logger.error(f"eBay error message: {error_match.group(1)}")
                break
            
            # Check for eBay API errors in the response
            ack_element = root.find(".//{urn:ebay:apis:eBLBaseComponents}Ack")
            if ack_element is not None:
                ack = ack_element.text
                if ack == "Failure" or ack == "Warning":
                    # Extract error messages
                    errors = []
                    for error in root.findall(".//{urn:ebay:apis:eBLBaseComponents}Errors"):
                        short_msg = error.findtext("{urn:ebay:apis:eBLBaseComponents}ShortMessage", "")
                        long_msg = error.findtext("{urn:ebay:apis:eBLBaseComponents}LongMessage", "")
                        error_code = error.findtext("{urn:ebay:apis:eBLBaseComponents}ErrorCode", "")
                        severity = error.findtext("{urn:ebay:apis:eBLBaseComponents}SeverityCode", "")
                        
                        if long_msg:
                            errors.append(f"Code {error_code} ({severity}): {long_msg}")
                    
                    if errors:
                        error_message = "; ".join(errors)
                        logger.error(f"eBay API returned errors: {error_message}")
                        
                        # Check for specific errors we should handle
                        if "Invalid token" in error_message or "Auth token" in error_message:
                            logger.error("Authentication failed - invalid access token")
                            return []  # Return empty to stop further processing
                        
                        # For pagination errors, stop gracefully
                        if "page number" in error_message.lower() or "pagination" in error_message.lower():
                            logger.info("Reached last page or pagination limit")
                            break
                    
                    break
            
            # Look for items with namespace
            page_items = root.findall(".//{urn:ebay:apis:eBLBaseComponents}Item")
            if not page_items:
                # Try alternative namespace
                page_items = root.findall(".//Item")
                
            if not page_items:
                logger.info(f"No items found on page {page}")
                break
            
            logger.info(f"Found {len(page_items)} items on page {page}")
            
            # Process items
            for item in page_items:
                # Helper function to safely extract text with namespace
                def find_text(element, path, default="N/A"):
                    # Try with namespace first
                    result = item.find(f".//{{urn:ebay:apis:eBLBaseComponents}}{path}")
                    if result is not None and result.text is not None:
                        return result.text.strip()
                    
                    # Try without namespace
                    result = item.find(f".//{path}")
                    if result is not None and result.text is not None:
                        return result.text.strip()
                    
                    return default
                
                # Extract all needed fields
                item_id = find_text(item, "ItemID", "Not Found")
                
                # Skip if item ID is invalid
                if item_id == "Not Found" or not item_id:
                    continue
                
                items.append({
                    "ebay_item_id": item_id,
                    "ebay_sku": find_text(item, "SKU", "N/A"),
                    "Title": find_text(item, "Title", "No Title"),
                    "ebay_price": find_text(item, "SellingStatus/CurrentPrice", "0"),
                    "ebay_quantity": find_text(item, "Quantity", "0"),
                    "quantity_sold": find_text(item, "SellingStatus/QuantitySold", "0"),
                    "ListingDuration": find_text(item, "ListingDuration", "N/A"),
                    "ListingType": find_text(item, "ListingType", "N/A"),
                    "PictureDetails": find_text(item, "PictureDetails/GalleryURL", "N/A"),
                    "ShippingProfileID": find_text(item, "SellerProfiles/SellerShippingProfile/ShippingProfileID", "N/A"),
                    "ShippingProfileName": find_text(item, "SellerProfiles/SellerShippingProfile/ShippingProfileName", "N/A"),
                    "ReturnProfileID": find_text(item, "SellerProfiles/SellerReturnProfile/ReturnProfileID", "N/A"),
                    "ReturnProfileName": find_text(item, "SellerProfiles/SellerReturnProfile/ReturnProfileName", "N/A"),
                    "PaymentProfileID": find_text(item, "SellerProfiles/SellerPaymentProfile/PaymentProfileID", "N/A"),
                    "PaymentProfileName": find_text(item, "SellerProfiles/SellerPaymentProfile/PaymentProfileName", "N/A"),
                    "market_item_url": find_text(item, "ViewItemURL", "N/A"),
                })
            
            # Check if there are more pages
            total_pages_elem = root.find(".//{urn:ebay:apis:eBLBaseComponents}PaginationResult/{urn:ebay:apis:eBLBaseComponents}TotalNumberOfPages")
            if total_pages_elem is not None and total_pages_elem.text:
                total_pages = int(total_pages_elem.text)
                if page >= total_pages:
                    logger.info(f"Reached last page ({page}/{total_pages})")
                    break
            else:
                # If we can't determine total pages and got items, assume there might be more
                if len(page_items) < 50:  # Less than max per page
                    logger.info("Received less than max items per page, assuming last page")
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
    
    if not user_tokens.exists():
        logger.warning("No eBay users with valid access tokens found")
        return {"status": "NO_USERS", "message": "No eBay users found"}
    
    total_all_users = 0
    
    for user in user_tokens:
        user_total = 0
        user_id = user.user_id
        
        logger.info(f"Starting eBay sync for user {user_id}")
        access_token = eb.refresh_access_token(user_id, "Ebay")
        try:
            end = datetime.utcnow().replace(microsecond=0)
            windows_processed = 0
            max_windows = months_back * 4
            
            for window_num in range(max_windows):
                # Calculate window
                start = end - timedelta(days=7)
                
                # Update task state
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "user_id": user_id,
                        "window": window_num + 1,
                        "total_windows": max_windows,
                        "items_processed": user_total,
                        "status": f"Processing window {window_num + 1}/{max_windows}"
                    }
                )
                
                logger.info(f"User {user_id}: Processing window {window_num + 1} ({start} to {end})")
                
                # Fetch items for this window
                try:
                    window_items = _fetch_window(
                        access_token,
                        start.isoformat() + "Z",  # Add Z for UTC
                        end.isoformat() + "Z"
                    )
                except Exception as fetch_error:
                    logger.error(f"Failed to fetch window for user {user_id}: {fetch_error}")
                    # If it's an auth error, stop processing this user
                    if "token" in str(fetch_error).lower() or "auth" in str(fetch_error).lower():
                        break
                    continue
                
                if not window_items:
                    logger.info(f"User {user_id}: No items in window {window_num + 1}")
                    if window_num == 0:
                        logger.warning(f"User {user_id}: No items found in recent window - check token permissions")
                    break
                
                logger.info(f"User {user_id}: Processing {len(window_items)} items from window {window_num + 1}")
                
                # Process items in smaller batches for database efficiency
                batch_size = 20
                for i in range(0, len(window_items), batch_size):
                    batch = window_items[i:i + batch_size]
                    
                    with transaction.atomic():
                        for item in batch:
                            try:
                                # Try to get existing item
                                try:
                                    existing_item = InventoryModel.objects.get(
                                        user_id=user_id,
                                        market_item_id=item["ebay_item_id"]
                                    )
                                    
                                    # Update basic info
                                    InventoryModel.objects.filter(
                                        user_id=user_id,
                                        market_item_id=item["ebay_item_id"]
                                    ).update(
                                        market_item_url=item["market_item_url"],
                                        last_updated=timezone.now()
                                    )
                                    
                                    # Check for price/quantity changes
                                    try:
                                        ebay_price = float(item["ebay_price"]) if item["ebay_price"] and item["ebay_price"] != "0" else 0
                                        ebay_quantity = int(item["ebay_quantity"]) if item["ebay_quantity"] and item["ebay_quantity"] != "0" else 0
                                        
                                        price_changed = float(existing_item.start_price or 0) != ebay_price
                                        quantity_changed = int(existing_item.quantity or 0) != ebay_quantity
                                        
                                        if price_changed or quantity_changed:
                                            logger.info(f"Price/quantity changed for item {item['ebay_item_id']}")
                                            # Call your update function here
                                            # update_items_quantity_or_price_on_ebay(...)
                                            
                                    except (ValueError, TypeError) as conv_error:
                                        logger.warning(f"Error converting price/quantity for item {item['ebay_item_id']}: {conv_error}")
                                        
                                except InventoryModel.DoesNotExist:
                                    # New item - get details
                                    try:
                                        product_details = get_item_details(user._id, item["ebay_item_id"])
                                        if not product_details:
                                            continue
                                        
                                        # Process and create new item (use your existing logic)
                                        # ... [your item creation logic here]
                                        
                                    except Exception as detail_error:
                                        logger.error(f"Failed to get details for new item {item['ebay_item_id']}: {detail_error}")
                                        continue
                                
                                user_total += 1
                                total_all_users += 1
                                
                            except Exception as item_error:
                                logger.error(f"Error processing item {item.get('ebay_item_id', 'Unknown')}: {item_error}")
                                continue
                    
                    # Update progress
                    if user_total % 50 == 0:
                        self.update_state(
                            state="PROGRESS",
                            meta={
                                "user_id": user_id,
                                "items_processed": user_total,
                                "total_items": total_all_users,
                                "status": f"Processed {user_total} items"
                            }
                        )
                
                windows_processed += 1
                end = start
                
                # Throttle between windows
                time.sleep(2)
                
                # Break if we've processed enough history
                if windows_processed >= 12:  # Limit to 12 weeks for performance
                    logger.info(f"User {user_id}: Reached history limit")
                    break
            
            logger.info(f"Completed eBay sync for user {user_id}: {user_total} items")
            
        except Exception as user_error:
            logger.exception(f"Fatal error processing user {user_id}: {user_error}")
            continue
    
    logger.info(f"Completed eBay sync for all users: {total_all_users} total items")
    
    return {
        "status": "SUCCESS",
        "total_items_processed": total_all_users,
        "users_processed": user_tokens.count(),
        "message": "eBay inventory sync completed"
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
