import requests, json
import time
import threading
from tenacity import retry, stop_after_attempt, wait_exponential
import xml.etree.ElementTree as ET
from marketplaceApp.models import MarketplaceEnronment
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from vendorEnrollment.utils import with_module
from accounts.permissions import IsOwnerOrHasPermission
from inventoryApp.utils import get_all_items_on_ebay, get_item_details
from rest_framework.response import Response
from rest_framework import status


EBAY_BASE = "https://api.ebay.com"
TRADING_URL = "https://api.ebay.com/ws/api.dll"

MAX_WORKERS = 5  # Keep small to avoid 429
REQUESTS_PER_SECOND = 5

lock = threading.Lock()
last_request_time = 0


# ---------------------------------------
#  Rate Limiter
# ---------------------------------------
def rate_limit():
    global last_request_time
    with lock:
        elapsed = time.time() - last_request_time
        if elapsed < 1 / REQUESTS_PER_SECOND:
            time.sleep((1 / REQUESTS_PER_SECOND) - elapsed)
        last_request_time = time.time()


# ---------------------------------------
#  Retry wrapper
# ---------------------------------------
@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=10))
def safe_request(method, url, **kwargs):
    rate_limit()
    response = requests.request(method, url, **kwargs)

    if response.status_code in [429, 500, 502, 503, 504]:
        raise Exception(f"Retryable error {response.status_code}")

    return response


# ---------------------------------------
# 1 Inventory Upsert
# ---------------------------------------
def upsert_inventory_item(access_token, sku, title, quantity):
    url = f"{EBAY_BASE}/sell/inventory/v1/inventory_item/{sku}"

    payload = {
        "product": {"title": title},
        "availability": {
            "shipToLocationAvailability": {"quantity": int(quantity)}
        }
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    safe_request("PUT", url, headers=headers, json=payload)


# ---------------------------------------
# 2 Create Offer
# ---------------------------------------
def create_offer(userid, sku, price, category_id, quantity, description):
    url = f"{EBAY_BASE}/sell/inventory/v1/offer"
    user_data = MarketplaceEnronment.objects.get(user_id=userid, marketplace_name="Ebay")
    access_token = user_data.access_token
    payload = {
        "sku": sku,
        "marketplaceId": "EBAY_US",
        "format": "FIXED_PRICE",
        "availableQuantity": int(quantity),
        "categoryId": category_id,
        "pricingSummary": {
            "price": {"value": price, "currency": "USD"}
        },
        "listingPolicies": {
            "fulfillmentPolicyId": json.loads(user_data.shipping_policy).get('id'),
            "paymentPolicyId": json.loads(user_data.payment_policy).get('id'),
            "returnPolicyId": json.loads(user_data.return_policy).get('id')
        },
        "listingDescription": description,

        "merchantLocationKey": "DEFAULT"
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = safe_request("POST", url, headers=headers, json=payload)
    return response.json().get("offerId")


# ---------------------------------------
# 3 Publish Offer
# ---------------------------------------
def publish_offer(access_token, offer_id):
    url = f"{EBAY_BASE}/sell/inventory/v1/offer/{offer_id}/publish"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    safe_request("POST", url, headers=headers)


# ---------------------------------------
# 4 Build Inventory Payload
# ---------------------------------------
def build_inventory_payload(item):
    product_item = get_item_details(item["enroll_id"], item["item_id"])
    # Put all the custom fields in the dictionary
    item_specific_fields = {}
    for object in product_item.get("localizedAspects"):
        item_specific_fields[object.get("name")] = [object.get("value")]
    payload = {
        "product": {
            "title": item["title"],
            "description": item["description"],
            "aspects": item_specific_fields,
            "imageUrls": item["images"]
        },
        "availability": {
            "shipToLocationAvailability": {
                "quantity": item["quantity"]
            }
        },
        "condition": "New"
    }

    # Optional identifiers
    if "Brand" in item_specific_fields:
        payload["product"]["brand"] = item_specific_fields["Brand"][0]

    if "MPN" in item_specific_fields:
        payload["product"]["mpn"] = item_specific_fields["MPN"][0]

    if "UPC" in item_specific_fields:
        payload["product"]["upc"] = item_specific_fields["UPC"][0]

    return payload



# ---------------------------------------------------
# 5 Create Inventory Item
# ---------------------------------------------------
def create_inventory_item(payload, userid):
    user_data = MarketplaceEnronment.objects.get(user_id=userid, marketplace_name="Ebay")
    access_token = user_data.access_token
    url = f"{EBAY_BASE}/sell/inventory/v1/inventory_item/{payload['product']['sku']}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = requests.put(url, headers=headers, json=payload)
    return response.status_code, response.text


# ---------------------------------------
#  Single Listing Migration
# ---------------------------------------
def migrate_single_listing(userid, listing):
    user_data = MarketplaceEnronment.objects.get(user_id=userid, marketplace_name="Ebay")
    try:
        sku = listing["sku"]
        if not sku:
            return f"Skipped {listing['item_id']} (No SKU)"

        upsert_inventory_item(access_token=user_data.access_token, sku=sku, title=listing["title"], quantity=listing["quantity"])
        offer_id = create_offer(userid, sku, listing["price"], listing["category_id"], listing["quantity"], listing["description"])
        payload = build_inventory_payload(listing)
        create_inventory = create_inventory_item(payload, userid)
        if offer_id and create_inventory[0] == 200:
            publish_offer(user_data.access_token, offer_id)

        return f"Success {sku}"

    except Exception as e:
        return f"Failed {listing.get('sku')} → {str(e)}"


# ---------------------------------------
#  Bulk Migration Controller
# ---------------------------------------
def migrate_bulk(userid, listings):
    for listing in listings:
        migrate_single_listing.delay(userid, listing)


@with_module('inventory')
@permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
@api_view(['GET'])
def start_migration_process(request, userid):
    # check if user is subaccount
    user = request.user
    if user:
        if user.parent_id:
            userid = user.parent_id
    try:
        user_data = MarketplaceEnronment.objects.get(user_id=userid, marketplace_name="Ebay")
        listings = get_all_items_on_ebay(user_data._id, user_data.access_token)

        migrate_bulk(userid, listings)
        return Response("Migration Started and will continue in the background", status=status.HTTP_200_OK)
            
    except Exception as e:
        return Response(f"Failed to start migration process. {e}", status=status.HTTP_400_BAD_REQUEST)