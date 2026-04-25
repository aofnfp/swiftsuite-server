import time, json, requests
from ratelimit import limits, sleep_and_retry
from django.apps import apps
from .models import InventoryModel, MarketPlaceUpdateLog, PriceQuantityUpdateLog
from vendorEnrollment.models import CwrUpdate, FragrancexUpdate, Generalproducttable, LipseyUpdate, RsrUpdate, SsiUpdate, ZandersUpdate, Enrollment
from django.db.models import Q
from marketplaceApp.models import MarketplaceEnronment
from woocommerce import API
import logging
logger = logging.getLogger(__name__)
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone


# Calculate the minimum offer price of product going to ebay
def calculated_minimum_offer_price(start_price, min_profit_mergin, profit_margin):
    try:
        minimum_offer_price = float(start_price) + float(profit_margin) + ((float(min_profit_mergin)/100) * float(start_price))
    except Exception as e:
        return Response(f"Failed to fetch data: Check your enrollment details", status=status.HTTP_400_BAD_REQUEST)
    return round(minimum_offer_price, 2)


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
    # calculate the minimum offer price based on the profit margin set by user
    if user_data.enable_best_offer == True:
        minimum_offer_price = calculated_minimum_offer_price(price, user_data.profit_margin, user_data.min_profit_mergin)
    else:
        minimum_offer_price = 0
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
                    <StartPrice>{str(price)}</StartPrice>
                    <Quantity>{str(quantity)}</Quantity>
                    <bestOfferEnabled>{user_data.enable_best_offer}</bestOfferEnabled>
                    <BestOfferDetails>
                    <BestOfferAutoAcceptPrice> {minimum_offer_price} </BestOfferAutoAcceptPrice>
                    <MinimumBestOfferPrice> {minimum_offer_price} </MinimumBestOfferPrice>
                    </BestOfferDetails>
                    <SellerProfiles>
                        <SellerPaymentProfile>
                            <PaymentProfileID>{json.loads(user_data.payment_policy).get('id')}</PaymentProfileID>
                        </SellerPaymentProfile>
                        <SellerReturnProfile>
                            <ReturnProfileID>{json.loads(user_data.return_policy).get('id')}</ReturnProfileID>
                        </SellerReturnProfile>
                        <SellerShippingProfile>
                            <ShippingProfileID>{json.loads(user_data.shipping_policy).get('id')}</ShippingProfileID>
                        </SellerShippingProfile>
                    </SellerProfiles>
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
                    <StartPrice>{str(price)}</StartPrice>
                    <bestOfferEnabled>{user_data.enable_best_offer}</bestOfferEnabled>
                    <BestOfferDetails>
                    <BestOfferAutoAcceptPrice> {minimum_offer_price} </BestOfferAutoAcceptPrice>
                    <MinimumBestOfferPrice> {minimum_offer_price} </MinimumBestOfferPrice>
                    </BestOfferDetails>
                    <SellerProfiles>
                        <SellerPaymentProfile>
                            <PaymentProfileID>{json.loads(user_data.payment_policy).get('id')}</PaymentProfileID>
                        </SellerPaymentProfile>
                        <SellerReturnProfile>
                            <ReturnProfileID>{json.loads(user_data.return_policy).get('id')}</ReturnProfileID>
                        </SellerReturnProfile>
                        <SellerShippingProfile>
                            <ShippingProfileID>{json.loads(user_data.shipping_policy).get('id')}</ShippingProfileID>
                        </SellerShippingProfile>
                    </SellerProfiles>
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
                    <Quantity>{str(quantity)}</Quantity>
                    <bestOfferEnabled>{user_data.enable_best_offer}</bestOfferEnabled>
                    <BestOfferDetails>
                    <BestOfferAutoAcceptPrice> {minimum_offer_price} </BestOfferAutoAcceptPrice>
                    <MinimumBestOfferPrice> {minimum_offer_price} </MinimumBestOfferPrice>
                    </BestOfferDetails>
                    <SellerProfiles>
                        <SellerPaymentProfile>
                            <PaymentProfileID>{json.loads(user_data.payment_policy).get('id')}</PaymentProfileID>
                        </SellerPaymentProfile>
                        <SellerReturnProfile>
                            <ReturnProfileID>{json.loads(user_data.return_policy).get('id')}</ReturnProfileID>
                        </SellerReturnProfile>
                        <SellerShippingProfile>
                            <ShippingProfileID>{json.loads(user_data.shipping_policy).get('id')}</ShippingProfileID>
                        </SellerShippingProfile>
                    </SellerProfiles>
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
            return f"Success:{response.text}"
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
            return f"Error{response.text}"
    except Exception as e:
        return f"Error: {e}"


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


# update items price and quantity on ebay and inventory with the one from the vendor
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
                        if db_item.map:
                            if selling_price < float(db_item.map):
                                selling_price = float(db_item.map)
                    except Exception as e:
                        print(f"selling price calculation error for SKU {item.sku}: {e}")
                        continue
                    # Check if the price and quantity of product on Ebay need to be updated
                    if item.start_price != round(selling_price, 2) or item.quantity != db_item.quantity:
                        # Check if the minimum quantity is lesser than supplier's quantity, use the minimum qauntity set by the user for the update, otherwise use the supplier's quantity for the update
                        if user.maximum_quantity:
                            if float(user.maximum_quantity) < float(db_item.quantity):
                                quantity = user.maximum_quantity
                            else:
                                quantity = db_item.quantity

                        response = update_items_quantity_or_price_on_ebay(user.user_id, item.market_item_id, round(selling_price, 2), quantity, user._id)
                        if "Success" in response:
                            item_to_save, created = MarketPlaceUpdateLog.objects.update_or_create(user_id=user.user_id, inventory_id=item.id, defaults=dict(market_name="Ebay", vendor_name=item.vendor_name, updated_sku=item.sku, log_description=f"Updated price to {round(selling_price, 2)} and quantity to {quantity} from vendor {item.vendor_name}"))
                            inventory, created = InventoryModel.objects.update_or_create(id=item.id, defaults=dict(start_price=round(selling_price, 2), quantity=f"eb:{quantity}|su:{db_item.quantity}", total_product_cost=db_item.total_product_cost, last_updated=timezone.now()))
                    # update inventory with the new price and quantity and log the update
                    item_to_save, created = PriceQuantityUpdateLog.objects.update_or_create(user_id=user.user_id, inventory_id=item.id, defaults=dict(market_name="Ebay", vendor_name=item.vendor_name, updated_sku=item.sku, log_description=f"Updated price to {round(selling_price, 2)} and quantity to {db_item.quantity} from vendor {item.vendor_name}"))
                except Exception as e:
                    print(f"Product fails to update price and quantity on Ebay: {e}")
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
                        if db_item.map and user.wc_map_enforcement==True:
                            if selling_price < float(db_item.map):
                                selling_price = float(db_item.map)
                    except Exception as e:
                        print(f"MAP enforcement error for SKU {item.sku}: {e} — using base price")
                    
                    # Update the price and quantity of product on Woocommerce
                    if item.start_price != round(selling_price, 2) or item.quantity != db_item.quantity:
                        response = update_woocommerce_product_from_background(item.market_item_id, round(selling_price, 2), db_item.quantity, user.user_id)
                        if response == "Success":
                            item_to_save, created = MarketPlaceUpdateLog.objects.update_or_create(user_id=user.user_id, inventory_id=item.id, defaults=dict(market_name="Woocommerce", vendor_name=item.vendor_name, updated_sku=item.sku, log_description=f"Updated price to {round(selling_price, 2)} and quantity to {db_item.quantity} from vendor {item.vendor_name}"))
                            inventory, created = InventoryModel.objects.update_or_create(id=item.id, defaults=dict(start_price=round(selling_price, 2), quantity=db_item.quantity, total_product_cost=db_item.total_product_cost, last_updated=timezone.now()))

                    # update inventory with the new price and quantity and log the update
                    item_to_save, created = PriceQuantityUpdateLog.objects.update_or_create(user_id=user.user_id, inventory_id=item.id, defaults=dict(market_name="Woocommerce", vendor_name=item.vendor_name, updated_sku=item.sku, log_description=f"Updated price to {round(selling_price, 2)} and quantity to {db_item.quantity} from vendor {item.vendor_name}"))
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


