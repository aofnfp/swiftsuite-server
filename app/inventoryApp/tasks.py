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
    items = []
    page = 1
    EBAY_URL = "https://api.ebay.com/ws/api.dll"

    NAMESPACE = {
        "ebay": "urn:ebay:apis:eBLBaseComponents"
    }

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

        response = requests.post(EBAY_URL, headers=HEADERS, data=body, timeout=30)

        if response.status_code != 200:
            break

        root = ET.fromstring(response.text)

        page_items = root.findall(".//e:Item", NAMESPACE)
        if not page_items:
            break

        for item in page_items:
            items.append({
                "ebay_item_id": item.findtext("e:ItemID", "Not Found", NAMESPACE),
                "ebay_sku": item.findtext("e:SKU", "N/A", NAMESPACE),
                "Title": item.findtext("e:Title", "No Title", NAMESPACE),
                "ebay_price": item.findtext("e:SellingStatus/e:CurrentPrice", "0", NAMESPACE),
                "ebay_quantity": item.findtext("e:Quantity", "0", NAMESPACE),
                "quantity_sold": item.findtext("e:SellingStatus/e:QuantitySold", "0", NAMESPACE),
                "ListingDuration": item.findtext("e:ListingDuration", "N/A", NAMESPACE),
                "ListingType": item.findtext("e:ListingType", "N/A", NAMESPACE),
                "PictureDetails": item.findtext("e:PictureDetails/e:GalleryURL", "N/A", NAMESPACE),
                "ShippingProfileID": item.findtext("e:SellerProfiles/e:SellerShippingProfile/e:ShippingProfileID", "N/A", NAMESPACE),
                "ShippingProfileName": item.findtext("e:SellerProfiles/e:SellerShippingProfile/e:ShippingProfileName", "N/A", NAMESPACE),
                "ReturnProfileID": item.findtext("e:SellerProfiles/e:SellerReturnProfile/e:ReturnProfileID", "N/A", NAMESPACE),
                "ReturnProfileName": item.findtext("e:SellerProfiles/e:SellerReturnProfile/e:ReturnProfileName", "N/A", NAMESPACE),
                "PaymentProfileID": item.findtext("e:SellerProfiles/e:SellerPaymentProfile/e:PaymentProfileID", "N/A", NAMESPACE),
                "PaymentProfileName": item.findtext("e:SellerProfiles/e:SellerPaymentProfile/e:PaymentProfileName", "N/A", NAMESPACE),
                "market_item_url": item.findtext(".//e:ViewItemURL", "N/A", NAMESPACE),
            })

        page += 1
        time.sleep(0.5)  # REQUIRED throttling

    return items


@shared_task(
    queue='heavy-inv',
    bind=True,
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3, "countdown": 30},
    rate_limit="6/m"
)
def download_item_update_market_price_quantity(self, months_back=12):

    user_token = MarketplaceEnronment.objects.all()
    for user in user_token:
        if user.marketplace_name != "Ebay":
            continue
        try:
            end = datetime.utcnow()
            total_processed = 0

            for _ in range(months_back * 4):  # 7-day windows
                start = end - timedelta(days=7)

                window_items = _fetch_window(user.access_token, start.isoformat(), end.isoformat())
                if not window_items:
                    break

                for item in window_items:
                    try:
                        existing_item = InventoryModel.objects.get(user_id=user.user_id, market_item_id=item["ebay_item_id"])

                        InventoryModel.objects.filter(user_id=user.user_id, market_item_id=item["ebay_item_id"]).update(market_item_url=item["market_item_url"], last_updated=timezone.now())
                        if (existing_item.start_price != item["ebay_price"] or existing_item.quantity != item["ebay_quantity"]):
                            update_items_quantity_or_price_on_ebay(user.user_id, item["ebay_item_id"], existing_item.start_price, existing_item.quantity, user._id)

                    except InventoryModel.DoesNotExist:
                        try:
                            product_details = get_item_details(user._id, item["ebay_item_id"])
                            if not product_details:
                                continue

                            for specific in product_details.get("localizedAspects"):
                                ebay_upc = specific.get("value") if specific.get("name") == "UPC" else ""
                                ebay_mpn = specific.get("value") if specific.get("name") == "MPN" else product_details.get("mpn") 

                            # Put all the custom fields in the dictionary
                            custom_fields = {}
                            for object in product_details.get("localizedAspects"):
                                custom_fields[object.get("name")] = object.get("value")
                                
                            inentory, created = InventoryModel.objects.update_or_create(user_id=user.user_id, market_item_id=item.get("ebay_item_id"), defaults={"title": item.get("Title"),"description": json.dumps(product_details.get("shortDescription")), "location": product_details.get("itemLocation")["country"], "category_id": product_details.get("categoryId"), "category": product_details.get("categoryPath"), "sku": item.get("ebay_sku"), "upc": ebay_upc, "mpn": ebay_mpn, "start_price": product_details.get("price")["value"], "price": product_details.get("price")["value"], "cost": product_details.get("price")["value"], "picture_detail": product_details.get("image")["imageUrl"], "thumbnailImage": product_details.get("additionalImages"), "postal_code": product_details.get("itemLocation")["postalCode"], "city": product_details.get("itemLocation")["city"], "country": product_details.get("itemLocation")["country"], "quantity": item.get("ebay_quantity"), "return_profileID": item.get("ReturnProfileID"), "return_profileName": item.get("ReturnProfileName"), "payment_profileID": item.get("PaymentProfileID"), "payment_profileName": item.get("PaymentProfileName"), "shipping_profileID": item.get("ShippingProfileID"), "shipping_profileName": item.get("ShippingProfileName"), "bestOfferEnabled": True, "listingType": item.get("ListingType"), "item_specific_fields": custom_fields, "market_logos": product_details.get("listingMarketplaceId"), "date_created": product_details.get("itemCreationDate").split("T")[0], "active": True, "vendor_name": "Not Found", "map_status": False, "market_name": "Ebay", "fixed_percentage_markup": user.fixed_percentage_markup, "fixed_markup": user.fixed_markup, "profit_margin": user.profit_margin, "min_profit_mergin": user.min_profit_mergin, "charity_id": user.charity_id, "enable_charity": user.enable_charity, "market_item_url": item.get("market_item_url")})

                        except Exception:
                            continue

                    total_processed += 1

                end = start
                time.sleep(1)  # window throttle

            self.update_state(
                state="PROGRESS",
                meta={"items_processed": total_processed}
            )

        except Exception as e:
            logger.exception(f"Ebay inventory sync failed: {e}")
            continue

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
