import time
from ratelimit import limits, sleep_and_retry
import requests
from django.apps import apps
from .models import InventoryModel
from vendorEnrollment.models import CwrUpdate, FragrancexUpdate, Generalproducttable, LipseyUpdate, RsrUpdate, SsiUpdate, ZandersUpdate, Enrollment
from django.db.models import Q
from marketplaceApp.models import MarketplaceEnronment
from woocommerce import API
import logging
logger = logging.getLogger(__name__)



# Function to check if ebay item has ended
# Limit to 5 calls per second (eBay's typical limit)
@sleep_and_retry
@limits(calls=5, period=1)
def check_if_ebay_item_has_ended(item_id, userid):
    try:
        user_data = MarketplaceEnronment.objects.get(user_id=userid, marketplace_name="Ebay")
    except Exception as e:
        print(f"Failed to fetch access token")
        return None
    
    url = "https://api.ebay.com/ws/api.dll"
    headers = {
        "X-EBAY-API-CALL-NAME": "GetItem",
        "X-EBAY-API-SITEID": "0",
        "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
        "X-EBAY-API-IAF-TOKEN": user_data.access_token,
        "Content-Type": "text/xml"
    }

    body = f"""
    <?xml version="1.0" encoding="utf-8"?>
    <GetItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
        <RequesterCredentials>
            <eBayAuthToken>{user_data.access_token}</eBayAuthToken>
        </RequesterCredentials>
        <ItemID>{item_id}</ItemID>
        <DetailLevel>ReturnAll</DetailLevel>
    </GetItemRequest>
    """

    try:
        response = requests.post(url, headers=headers, data=body)
        if response.status_code == 429:  # Rate limit hit
            retry_after = int(response.headers.get('Retry-After', 2))
            time.sleep(retry_after)
            return check_if_ebay_item_has_ended(item_id, userid)
        
        if response.status_code != 200:
            return None

        xml = response.text
        if "<ListingStatus>Completed</ListingStatus>" in xml:
            # Check if it sold
            if "<SellingStatus>" in xml and "<QuantitySold>0</QuantitySold>" not in xml:
                return "sold out"
            else:
                return "Deleted"
        return "active"
    except Exception as e:
        print(f"Error: {e}")
        return None


# update items price and quantity on ebay and inventory with the from the vendor
def update_inventory_price_quantity():
    # Get all user with ebay marketplace to sync their products
    user_token = MarketplaceEnronment.objects.all() # get all user to get their access_token
    for user in user_token:
        if user.marketplace_name == "Ebay":
            all_ebay_items = InventoryModel.objects.filter(user_id=user.user_id, market_name="Ebay").exclude(vendor_name="Not Found")
                
            for item in all_ebay_items:
                try:
                    # Get updated price and quantity from the product table
                    try:
                        db_item = Generalproducttable.objects.get(id=item.product_id)
                    except Exception as e:
                        print(f"item not found on product table: {e} with sku {item.sku}")
                        continue
                    
                    # Modify selling price before updating on ebay
                    try:
                        selling_price = float(db_item.total_product_cost) + float(user.fixed_markup) + ((float(user.fixed_percentage_markup)/100) * float(db_item.total_product_cost)) + ((float(user.profit_margin)/100) * float(db_item.total_product_cost))
                    except Exception as e:
                        print(f"Base price calculation error for SKU {item.sku}: {e}")
                        continue
                    try:
                        if db_item.map:
                            if selling_price < float(db_item.map):
                                selling_price = float(db_item.map)
                    except Exception as e:
                        print(f"MAP enforcement error for SKU {item.sku}: {e} — using base price")
                    # update inventory with the new price and quantity and log the update
                    inventory, created = InventoryModel.objects.update_or_create(id=item.id, defaults=dict(start_price=round(selling_price, 2), quantity=db_item.quantity, total_product_cost=db_item.total_product_cost))

                except Exception as e:
                    print(f"Product fails to update price and quantity on ebay: {e}")
                    continue

        elif user.marketplace_name == "Woocommerce":
            # Fetch all item from Woocommerce
            all_woocommercer_items = InventoryModel.objects.filter(user_id=user.user_id, market_name="Woocommerce").exclude(vendor_name="Not Found")
            for item in all_woocommercer_items:
                try:
                    # Get updated price and quantity from the product table
                    try:
                        db_item = Generalproducttable.objects.get(id=item.product_id)
                    except Exception as e:
                        print(f"item not found on product table: {e}")
                        continue

                    # Modify selling price before updating on Woocommerce
                    try:
                        selling_price = float(db_item.total_product_cost) + float(user.fixed_markup) + ((float(user.fixed_percentage_markup)/100) * float(db_item.total_product_cost)) + ((float(user.profit_margin)/100) * float(db_item.total_product_cost))
                    except Exception as e:
                        print(f"Base price calculation error for SKU {item.sku}: {e}")
                        continue
                    try:
                        if db_item.map:
                            if selling_price < float(db_item.map):
                                selling_price = float(db_item.map)
                    except Exception as e:
                        print(f"MAP enforcement error for SKU {item.sku}: {e} — using base price")

                    # update inventory with the new price and quantity and log the update
                    inventory, created = InventoryModel.objects.update_or_create(id=item.id, defaults=dict(start_price=round(selling_price, 2), quantity=db_item.quantity, total_product_cost=db_item.total_product_cost))
                except Exception as e:
                    print(f"Product fails to update price and quantity on Woocommerce: {e}")
                    continue


# function to check and update ended ebay items in the inventory
def check_product_ended_status():
    # Get all user with ebay marketplace to sync their products
    user_token = MarketplaceEnronment.objects.all() # get all user to get their access_token
    for user in user_token:
        if user.marketplace_name == "Ebay":
            all_ebay_items = InventoryModel.objects.filter(user_id=user.user_id, market_name="Ebay").exclude(market_item_id="")
                
            for item in all_ebay_items:
                try:
                    # Check if ebay item has ended
                    ends_status = check_if_ebay_item_has_ended(item.market_item_id, user.user_id)
                    if ends_status is None:
                        continue

                    inventory, created = InventoryModel.objects.update_or_create(id=item.id, defaults=dict(ends_status=ends_status))
                except Exception as e:
                    print(f"Failed to check and update ended ebay items: {e}")
                    continue
        
        elif user.marketplace_name == "Woocommerce":
            all_ebay_items = InventoryModel.objects.filter(user_id=user.user_id, market_name="Woocommerce").exclude(market_item_id="")
                
            for item in all_ebay_items:    
                try: 
                    # Check if ebay item has ended
                    pass
                except Exception as e:
                    print(f"Failed to update woocommerce items: {e}")
                    continue


            
     