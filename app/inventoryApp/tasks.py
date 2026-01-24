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
from .models import InventoryModel, UpdateLogModel
from .utils import get_all_items_on_ebay, get_item_details, update_items_quantity_or_price_on_ebay
from marketplaceApp.models import MarketplaceEnronment
from django.utils import timezone
import json


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



# Download all items from all marketplace to local inventory

@shared_task(
    queue='heavy-inv',
    bind=True,
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3, "countdown": 30},
    rate_limit="6/m"
)
def download_item_update_market_price_quantity(self):
    all_ebay_items = []

    # Get all user with ebay marketplace to sync their products
    user_token = MarketplaceEnronment.objects.all() # get all user to get their access_token
    for user in user_token:
        # Deal with ebay marketplace
        if user.marketplace_name == "Ebay":
            # Fetch all eBay items by walking backward in 30-day windows
            try:
                all_ebay_items = get_all_items_on_ebay(enroll_id=user._id)

            except Exception as e:
                logger.info(f"Ebay inventory download failed with error: {e}")
                continue

            # If fetching items failed due to invalid token, try refreshing token once and fetch again
            if all_ebay_items == None:
                logger.info(f"Ebay inventory download failed with error: {all_ebay_items}")
                continue
            # Construct a list of ebay items with relevant details
            for item in all_ebay_items:
                all_ebay_items.append({"ebay_item_id":item[0], "ebay_sku":item[1], 'Title':item[2], "ebay_price":item[3], "ebay_quantity":item[4], 'ListingDuration':item[5], 'ListingType':item[6], 'PictureDetails':item[7], 'ShippingProfileID':item[8], 'ShippingProfileName':item[9], 'ReturnProfileID':item[10], 'ReturnProfileName':item[11], 'PaymentProfileID':item[12], 'PaymentProfileName':item[13], 'market_item_url':item[14]})
            logger.info(f"Ebay inventory download fetched {len(all_ebay_items)} items for user {user.user_id}")
            # Loop through each item and update or insert into InventoryModel
            for item in all_ebay_items:                         
                try:
                    # If item already exists, skip to next item
                    existing_item = InventoryModel.objects.get(user_id=user.user_id, market_item_id=item.get("ebay_item_id"))
                    # Update the market url on inventory
                    InventoryModel.objects.filter(user_id=user.user_id, market_item_id=item.get("ebay_item_id")).update(market_item_url=item.get("market_item_url"), last_updated=timezone.now())
                    if existing_item.market_item_id == "" or existing_item.vendor_name == "Not Found":
                        continue
                    # Update the price and quantity of product on Ebay
                    if existing_item.start_price != item.get("ebay_price") or existing_item.quantity != item.get("ebay_quantity"):
                        response = update_items_quantity_or_price_on_ebay(user.user_id, item.get("ebay_item_id"), existing_item.start_price, existing_item.quantity, user._id)
                        item_to_save, created = UpdateLogModel.objects.update_or_create(user_id=user.user_id, inventory_id=existing_item.id, defaults=dict(market_name="Ebay", vendor_name=existing_item.vendor_name, updated_item=item.sku, log_description=f"Updated price to {existing_item.start_price} and quantity to {existing_item.quantity} from vendor {existing_item.vendor_name}"))

                except:
                    try:
                        # Get product details from eBay
                        product_details = get_item_details(user._id, item.get("ebay_item_id"))
                        if product_details == None:
                            logger.info(f"Ebay get product details failed for item id {item.get('ebay_item_id')} with error: {product_details}")
                            continue
                        else:
                            logger.info(f"Ebay get product details succeeded for item id {item.get('ebay_item_id')}")
                            # Get the upc and mpn if the main mpn field does not exist
                            for specific in product_details.get("localizedAspects"):
                                ebay_upc = specific.get("value") if specific.get("name") == "UPC" else ""
                                ebay_mpn = specific.get("value") if specific.get("name") == "MPN" else product_details.get("mpn") 

                            # Put all the custom fields in the dictionary
                            custom_fields = {}
                            for object in product_details.get("localizedAspects"):
                                custom_fields[object.get("name")] = object.get("value")
                                
                            inentory, created = InventoryModel.objects.update_or_create(user_id=user.user_id, market_item_id=item.get("ebay_item_id"), defaults={"title": item.get("Title"),"description": json.dumps(product_details.get("shortDescription")), "location": product_details.get("itemLocation")["country"], "category_id": product_details.get("categoryId"), "category": product_details.get("categoryPath"), "sku": item.get("ebay_sku"), "upc": ebay_upc, "mpn": ebay_mpn, "start_price": product_details.get("price")["value"], "price": product_details.get("price")["value"], "cost": product_details.get("price")["value"], "picture_detail": product_details.get("image")["imageUrl"], "thumbnailImage": product_details.get("additionalImages"), "postal_code": product_details.get("itemLocation")["postalCode"], "city": product_details.get("itemLocation")["city"], "country": product_details.get("itemLocation")["country"], "quantity": item.get("ebay_quantity"), "return_profileID": item.get("ReturnProfileID"), "return_profileName": item.get("ReturnProfileName"), "payment_profileID": item.get("PaymentProfileID"), "payment_profileName": item.get("PaymentProfileName"), "shipping_profileID": item.get("ShippingProfileID"), "shipping_profileName": item.get("ShippingProfileName"), "bestOfferEnabled": True, "listingType": item.get("ListingType"), "item_specific_fields": custom_fields, "market_logos": product_details.get("listingMarketplaceId"), "date_created": product_details.get("itemCreationDate").split("T")[0], "active": True, "vendor_name": "Not Found", "map_status": False, "market_name": "Ebay", "fixed_percentage_markup": user.fixed_percentage_markup, "fixed_markup": user.fixed_markup, "profit_margin": user.profit_margin, "min_profit_mergin": user.min_profit_mergin, "charity_id": user.charity_id, "enable_charity": user.enable_charity, "market_item_url": item.get("market_item_url")})
                    except Exception as e:
                        logger.info(f"Ebay Product failed to insert into inventory {e}")
                        continue




