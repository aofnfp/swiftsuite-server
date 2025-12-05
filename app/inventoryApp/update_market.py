import json, time
from ratelimit import limits, sleep_and_retry
import requests
from rest_framework.decorators import api_view, permission_classes
from ebaysdk.exception import ConnectionError
from .models import InventoryModel, UpdateLogModel
from marketplaceApp.views import Ebay
from vendorEnrollment.models import CwrUpdate, FragrancexUpdate, Generalproducttable, LipseyUpdate, RsrUpdate, SsiUpdate, ZandersUpdate
from marketplaceApp.models import MarketplaceEnronment
from django.db.models import Q
from woocommerce import API
from .utils import calculated_selling_price


# Create a function to update items quantity and price at the background on Ebay
# Limit to 5 calls per second (eBay's typical limit)
@sleep_and_retry
@limits(calls=5, period=1)
def update_items_quantity_or_price_on_ebay(user_id, item_id, price, quantity, enroll_id):
    try:
        user_data = MarketplaceEnronment.objects.get(_id=enroll_id, marketplace_name="Ebay")
    except Exception as e:
        print(f"Failed to fetch access token")
        return None
    
    access_token =  user_data.access_token
    
    # eBay Trading API endpoint
    url = 'https://api.ebay.com/ws/api.dll'

    headers = {
        'X-EBAY-API-CALL-NAME': 'ReviseItem',
        'X-EBAY-API-SITEID': '0',  # Change this to your site ID, 0 is for US
        'X-EBAY-API-COMPATIBILITY-LEVEL': '1081',  # eBay API version
        'Content-Type': 'text/xml',
        'Authorization': f'Bearer {access_token}'
    }
    try:
        # XML Body for ReviseItem request
        if user_data.enable_price_update == True and user_data.enable_quantity_update == True:
            body = f"""
            <?xml version="1.0" encoding="utf-8"?>
            <ReviseItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
                <RequesterCredentials>
                    <eBayAuthToken>{access_token}</eBayAuthToken>
                </RequesterCredentials>
                <Item>
                    <ItemID>{item_id}</ItemID>
                    <StartPrice>{price,}</StartPrice>
                    <Quantity>{quantity}</Quantity>
                </Item>
            </ReviseItemRequest>
            """
        elif user_data.enable_price_update == True and user_data.enable_quantity_update == False:
            body = f"""
            <?xml version="1.0" encoding="utf-8"?>
            <ReviseItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
                <RequesterCredentials>
                    <eBayAuthToken>{access_token}</eBayAuthToken>
                </RequesterCredentials>
                <Item>
                    <ItemID>{item_id}</ItemID>
                    <StartPrice>{price}</StartPrice>
                </Item>
            </ReviseItemRequest>
            """
        elif user_data.enable_price_update == False and user_data.enable_quantity_update == True:
            body = f"""
            <?xml version="1.0" encoding="utf-8"?>
            <ReviseItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
                <RequesterCredentials>
                    <eBayAuthToken>{access_token}</eBayAuthToken>
                </RequesterCredentials>
                <Item>
                    <ItemID>{item_id}</ItemID>
                    <Quantity>{quantity}</Quantity>
                </Item>
            </ReviseItemRequest>
            """
        else:
            return None
        
        # Make the POST request
        response = requests.post(url, headers=headers, data=body)
        if response.status_code == 429:  # Rate limit hit
            retry_after = int(response.headers.get('Retry-After', 2))
            time.sleep(retry_after)
            return update_items_quantity_or_price_on_ebay(user_id, item_id, price, quantity, enroll_id)
        # Check the response
        if response.status_code == 200:
            return f"Success: {response.text}"
        else:
            return f"Error:{response.text}"
    except ConnectionError as e:
        return f'Error: {e}'
    

# Function to update product on woocommerce store
# Limit to 5 calls per second (eBay's typical limit)
@sleep_and_retry
@limits(calls=5, period=1)
def update_woocommerce_product_from_background(market_item_id, selling_price, quantity, userid):
    try:
        enrollment = MarketplaceEnronment.objects.get(user_id=userid, marketplace_name="Woocommerce")
        # Set up the WooCommerce API client
        wcapi = API(
            url = enrollment.wc_consumer_url, 
            consumer_key = enrollment.wc_consumer_key,  
            consumer_secret = enrollment.wc_consumer_secret, 
            version = "wc/v3"
        )
        # Product payload mapped to WooCommerce
        update_data = {
            "type": "simple",
            "regular_price": selling_price,
            "stock_quantity": quantity,
            "manage_stock": True,
        }

        # --- MAKE THE UPDATE REQUEST ---
        response = wcapi.put(f"products/{market_item_id}", update_data)
        if response.status_code == 429:  # Rate limit hit
            retry_after = int(response.headers.get('Retry-After', 2))
            time.sleep(retry_after)
            return update_woocommerce_product_from_background(market_item_id, selling_price, quantity, userid)
        if response.status_code == 200:
            return "Success"
        else:
            print(f"Error: Woocommerce update fails. Status code: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print(f"Error: Error from the try block woocommerce update. {e}")
        return None


# update items price and quantity on ebay and inventory with the from the vendor
def update_ebay_price_quantity():
    eb = Ebay()
    # Get all user with ebay marketplace to sync their products
    user_token = MarketplaceEnronment.objects.all() # get all user to get their access_token
    for user in user_token:
        if user.marketplace_name == "Ebay":
            all_ebay_items = InventoryModel.objects.filter(user_id=user.user_id, market_name="Ebay")
                
            for item in all_ebay_items:
                # Check if the item has a vendor mapped to it
                if item.vendor_name.lower() == "not found":
                    continue
                try:
                    # Get updated price and quantity from the product table
                    try:
                        db_item = Generalproducttable.objects.get(id=item.product_id)
                    except Exception as e:
                        print(f"item not found on product table: {e}")
                        continue
                    
                    # Modify selling price before updating on ebay 
                    cost_computation = calculated_selling_price(market_id=user._id, total_product_cost=db_item.total_product_cost, userid=user.user_id, map=db_item.map)
                    if cost_computation == None:
                        continue
                    selling_price, total_product_cost = cost_computation
                    # Item exists, check if we need to update price or quantity
                    InventoryModel.objects.filter(id=item.id).update(start_price=selling_price, quantity=db_item.quantity, total_product_cost=total_product_cost)
                    # Update the product on Ebay
                    response = update_items_quantity_or_price_on_ebay(user.user_id, item.market_item_id, selling_price, db_item.quantity, user._id)
                    item_to_save, created = UpdateLogModel.objects.update_or_create(user_id=item.user_id, inventory_id=item.id, defaults=dict(market_name="Ebay", vendor_name=item.vendor_name, updated_item=item.sku, log_description=f"Updated price to {selling_price} and quantity to {db_item.quantity} from vendor {item.vendor_name}"))
                    

                except Exception as e:
                    print(f"Product fails to update price and quantity on ebay: {e}")
                    continue

        elif user.marketplace_name == "Woocommerce":
            # Fetch all item from Woocommerce
            all_woocommercer_items = InventoryModel.objects.filter(user_id=user.user_id, market_name="Woocommerce")
            for item in all_woocommercer_items:
                # Check if the item has a vendor mapped to it
                if item.vendor_name.lower() == "not found":
                    continue
                try:
                    # Get updated price and quantity from the product table
                    try:
                        db_item = Generalproducttable.objects.get(id=item.product_id)
                    except Exception as e:
                        print(f"item not found on product table: {e}")
                        continue 
                    # Modify selling price before updating on ebay 
                    cost_computation = calculated_selling_price(market_id=user._id, total_product_cost=db_item.total_product_cost, userid=user.user_id, map=db_item.map)
                    if cost_computation == None:
                        continue
                    selling_price, total_product_cost = cost_computation
                    # Item exists, check if we need to update price or quantity
                    InventoryModel.objects.filter(id=item.id).update(start_price=selling_price, quantity=db_item.quantity, total_product_cost=total_product_cost)
                    # Update the product on Woocommerce
                    response = update_woocommerce_product_from_background(item.market_item_id, selling_price, db_item.quantity, user.user_id)
                    item_to_save, created = UpdateLogModel.objects.update_or_create(user_id=item.user_id, inventory_id=item.id, defaults=dict(market_name="Woocommerce", vendor_name=item.vendor_name, updated_item=item.sku, log_description=f"Updated price to {selling_price} and quantity to {db_item.quantity} from vendor {item.vendor_name}"))
                
                except Exception as e:
                    print(f"Product fails to update price and quantity on Woocommerce: {e}")
                    continue