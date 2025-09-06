import requests, time
import base64
from marketplaceApp.views import Ebay
from marketplaceApp.models import MarketplaceEnronment
from ratelimit import limits, sleep_and_retry
from .models import OrdersOnEbayModel
from inventoryApp.models import InventoryModel



# Function to refresh the access token using the refresh token
def refresh_access_token_for_sync(market_id, market_name):
    eb = Ebay()
    try:
        connection = MarketplaceEnronment.objects.all().get(_id=market_id, marketplace_name=market_name)
    except Exception as e:
        print(f"Failed to fetch access token in orderapp: {e}")
        return None
    
    access_token = connection.access_token
    refresh_token = connection.refresh_token

    credentials = f"{eb.client_id}:{eb.client_secret}"
    credentials_base64 = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {credentials_base64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    body = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": " ".join(eb.scopes)  # Ensure scope is passed correctly
    }

    response = requests.post(eb.token_url, headers=headers, data=body)
    if response.status_code != 200:
        print(f"Failed to refresh access token. Authorization code has expired: {response.text}")

    result = response.json()
    access_token = result.get('access_token')
    
    if not access_token:
        print(f"Failed to get access token from response{result}")

    MarketplaceEnronment.objects.filter(_id=market_id, marketplace_name=market_name).update(access_token=access_token, refresh_token=refresh_token)
    return access_token


# Function to retrieve all fulfilment orders from Ebay
def get_product_ordered_from_background(access_token):
    
    # Set eBay API endpoint and headers
    try:
        url = "https://api.ebay.com/sell/fulfillment/v1/order"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        orders = []
        offset = 0
        limit = 50  # Adjust the limit as needed
        
        while True:
            params = {
                "limit": limit,
                "offset": offset
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                orders.extend(data.get('orders', []))
                
                if len(data.get('orders', [])) < limit:
                    break  # No more orders to fetch
                offset += limit
            else:
                print(f"Failed to retrieve orders: {response.text}")
        
        return orders  
    except Exception as e:
        print(f'Could not fetch ordered items from ebay Error: {e}')
        return None
        

# Function to get details of specific item ordered on ebay
# Limit to 5 calls per second (eBay's typical limit)
@sleep_and_retry
@limits(calls=5, period=1)
def get_item_ordered_details(access_token, item_id):
    """Fetch detailed product information (UPC, EAN, Brand, etc.) using GetItem API."""
    # Set up the headers with the access token
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    # get full product details of the item ordered
    item_url = f"https://api.ebay.com/buy/browse/v1/item/get_item_by_legacy_id?legacy_item_id={item_id}"
    response = requests.get(item_url, headers=headers)
    if response.status_code == 429:  # Rate limit hit
        retry_after = int(response.headers.get('Retry-After', 2))
        time.sleep(retry_after)
        return get_item_ordered_details(access_token, item_id)
        
    product_data = response.json()
    if response.status_code == 200:
        return product_data
    else:
        print(f"Failed to retrieve details for Item ID {item_id}: {response.text}")
        return None
        

# Update orders on ebay to the one on local database at the background
# @api_view(["GET"])
def sync_ebay_order_with_local():
    user_token = MarketplaceEnronment.objects.all() # get all user to get their access_token and user id
    for user in user_token:
        # Get access_token
        access_token = refresh_access_token_for_sync(user._id, "Ebay") #requests.get(f"https://service.swiftsuite.app/marketplaceApp/get_refresh_access_token/{user.id}/Ebay")
        if not access_token:
            print(f"Failed to refresh access token. Access token returns none in orderapp")
            continue
            
        # Fetch all orders from eBay
        ebay_orders = get_product_ordered_from_background(access_token)
        if ebay_orders == None:
            print(f"Failed to fetch ordered items from ebay for user {user.user_id}")
            continue
        
        for order in ebay_orders:
            # Check if order already exists on local database else insert it
            try:
                lineItems = order.get('lineItems', [])[0]
                ebay_order_id = order.get("orderId")
                exist_order = OrdersOnEbayModel.objects.get(orderId=ebay_order_id)
                product_data = InventoryModel.objects.all().filter(ebay_item_id=lineItems.get("legacyItemId"))
                if len(product_data) == 0:
                    product_data = {"vendor_name":""}
                else:
                    product_data = product_data.values()[0]
                OrdersOnEbayModel.objects.filter(orderId=ebay_order_id).update(orderFulfillmentStatus=order.get("orderFulfillmentStatus"), orderPaymentStatus=order.get("orderPaymentStatus"), vendor_name=product_data.get('vendor_name'))
            except:
                try:
                    lineItems = order.get('lineItems', [])[0]
                    product_data = InventoryModel.objects.all().filter(ebay_item_id=lineItems.get("legacyItemId"))
                    if len(product_data) == 0:
                        print(f"product details returned None in orderApp for item with item_id {order.get('ebay_item_id')}")
                        continue
                    else:
                        product_data = product_data.values()[0]
                    save_order = OrdersOnEbayModel(user_id=user.user_id, orderId=order.get("orderId"),
                                                legacyOrderId=order.get("legacyOrderId"), creationDate=order.get("creationDate"),
                                                orderFulfillmentStatus=order.get("orderFulfillmentStatus"), orderPaymentStatus=order.get("orderPaymentStatus"),
                                                sellerId=order.get("sellerId"), buyer=order.get("buyer"), cancelStatus=order.get("cancelStatus"),
                                                pricingSummary=order.get("pricingSummary"), paymentSummary=order.get("paymentSummary"), 
                                                fulfillmentStartInstructions=order.get("fulfillmentStartInstructions"), sku=lineItems.get("sku"), title=lineItems.get("title"),
                                                lineItemCost=lineItems.get("lineItemCost"), quantity=lineItems.get("quantity"),
                                                listingMarketplaceId=lineItems.get("listingMarketplaceId"), purchaseMarketplaceId=lineItems.get("purchaseMarketplaceId"),
                                                itemLocation=lineItems.get("itemLocation"), legacyItemId=lineItems.get('legacyItemId'), image=product_data.get("picture_detail"),
                                                additionalImages=product_data.get("thumbnailImage"), description=product_data.get("description"), categoryId=product_data.get("category_id"),
                                                ebayItemId=product_data.get("ebay_item_id"), localizeAspects=product_data.get("item_specific_fields"), vendor_name=product_data.get('vendor_name'))
                    save_order.save()
                except Exception as e:
                    print(f"Ordered item insert error {e} ")
                    



