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
            "regular_price": str(selling_price),
            "stock_quantity": str(quantity),
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
def update_inventory_price_quantity():
    # Get all user with ebay marketplace to sync their products
    user_token = MarketplaceEnronment.objects.all() # get all user to get their access_token
    for user in user_token:
        if user.marketplace_name == "Ebay":
            all_ebay_items = InventoryModel.objects.filter(user_id=user.user_id, market_name="Ebay")
                
            for item in all_ebay_items:
                # Check if the item has a vendor mapped to it
                if item.vendor_name.lower() == "not found" or item.manual_map == True:
                    continue
                try:
                    # Get updated price and quantity from the product table
                    try:
                        db_item = Generalproducttable.objects.get(id=item.product_id)
                    except Exception as e:
                        print(f"item not found on product table: {e}")
                        continue
                    
                    # Modify selling price before updating on ebay 
                    try:
                        selling_price = float(db_item.total_product_cost) + float(user.fixed_markup) + ((float(user.fixed_percentage_markup)/100) * float(db_item.total_product_cost)) + ((float(user.profit_margin)/100) * float(db_item.total_product_cost))
                        if db_item.map:
                            if selling_price < float(db_item.map):
                                selling_price = float(db_item.map)
                    except:
                        print("Price calculation error with MAP value") 
                        continue
                    # update inventory with the new price and quantity and log the update
                    inventory, created = InventoryModel.objects.update_or_create(id=item.id, defaults=dict(start_price=round(selling_price, 2), quantity=db_item.quantity, total_product_cost=db_item.total_product_cost))
                    item_to_save, created = UpdateLogModel.objects.update_or_create(user_id=item.user_id, inventory_id=item.id, defaults=dict(market_name="Ebay", vendor_name=item.vendor_name, updated_item=item.sku, log_description=f"Updated price to {round(selling_price, 2)} and quantity to {db_item.quantity} from vendor {item.vendor_name}"))

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
                    try:
                        selling_price = float(db_item.total_product_cost) + float(user.fixed_markup) + ((float(user.fixed_percentage_markup)/100) * float(db_item.total_product_cost)) + ((float(user.profit_margin)/100) * float(db_item.total_product_cost))
                        if db_item.map:
                            if selling_price < float(db_item.map):
                                selling_price = float(db_item.map)
                    except:
                        print("Price calculation error with MAP value") 
                        continue
                    
                    # update inventory with the new price and quantity and log the update
                    inventory, created = InventoryModel.objects.update_or_create(id=item.id, defaults=dict(start_price=round(selling_price, 2), quantity=db_item.quantity, total_product_cost=db_item.total_product_cost))
                    item_to_save, created = UpdateLogModel.objects.update_or_create(user_id=item.user_id, inventory_id=item.id, defaults=dict(market_name="Woocommerce", vendor_name=item.vendor_name, updated_item=item.sku, log_description=f"Updated price to {round(selling_price, 2)} and quantity to {db_item.quantity} from vendor {item.vendor_name}"))                
                except Exception as e:
                    print(f"Product fails to update price and quantity on Woocommerce: {e}")
                    continue


# function to check and update ended ebay items in the inventory
def check_ended_status_update_quantity_price():
    # Get all user with ebay marketplace to sync their products
    user_token = MarketplaceEnronment.objects.all() # get all user to get their access_token
    for user in user_token:
        if user.marketplace_name == "Ebay":
            all_ebay_items = InventoryModel.objects.filter(user_id=user.user_id, market_name="Ebay")
                
            for item in all_ebay_items:
                # Check if the item has a vendor mapped to it
                if item.market_item_id == "" or item.vendor_name == "Not Found":
                    continue
                try:
                    # Check if ebay item has ended
                    ends_status = check_if_ebay_item_has_ended(item.market_item_id, user.user_id)
                    if ends_status is None:
                        continue

                    # Update the price and quantity of product on Ebay
                    response = update_items_quantity_or_price_on_ebay(user.user_id, item.market_item_id, item.start_price, item.quantity, user._id)

                    inventory, created = InventoryModel.objects.update_or_create(id=item.id, defaults=dict(ends_status=ends_status))
                    item_to_save, created = UpdateLogModel.objects.update_or_create(user_id=item.user_id, inventory_id=item.id, defaults=dict(market_name="Ebay", vendor_name=item.vendor_name, updated_item=item.sku, log_description=f"Ebay item availability status changed to {ends_status}"))
                except Exception as e:
                    print(f"Failed to check and update ended ebay items: {e}")
                    continue
        
        elif user.marketplace_name == "Woocommerce":
            all_ebay_items = InventoryModel.objects.filter(user_id=user.user_id, market_name="Woocommerce")
                
            for item in all_ebay_items:
                    
                # Update the product on Woocommerce
                try: 
                    if item.market_item_id == "" or item.vendor_name == "Not Found":
                        continue
                    # Update the price and quantity of product on Woocommerce
                    response = update_woocommerce_product_from_background(item.market_item_id,item.start_price, item.quantity, user.user_id)

                    inventory, created = InventoryModel.objects.update_or_create(id=item.id, defaults=dict(start_price=item.start_price))
                    # Check if the item has a vendor mapped to it
                except Exception as e:
                    print(f"Failed to update woocommerce items: {e}")
                    continue


