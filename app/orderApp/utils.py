import requests, time
from marketplaceApp.views import Ebay
from marketplaceApp.models import MarketplaceEnronment
from ratelimit import limits, sleep_and_retry
from .models import OrdersOnEbayModel
from inventoryApp.models import InventoryModel
from datetime import datetime, timedelta
from woocommerce import API
import logging
from vendorEnrollment.models import Enrollment
from .models import VendorOrderLog
from rest_framework.decorators import api_view

logger = logging.getLogger(__name__)
from vendorEnrollment.models import Generalproducttable


# Function to retrieve all fulfilment orders from Ebay
def get_product_ordered_from_background(userid, enroll_id):
    # Get access_token
    try:
        user_data = MarketplaceEnronment.objects.get(_id=enroll_id, marketplace_name="Ebay")  # requests.get(f"https://service.swiftsuite.app/marketplaceApp/get_refresh_access_token/{user.id}/Ebay")
    except Exception as e:
        print(f"Failed to fetch access token")
        return None
    
    access_token =  user_data.access_token 
    try:
        HEADERS = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        base_url = "https://api.ebay.com/sell/fulfillment/v1/order"
        limit = 100
        offset = 0
        all_orders = []

        start_time = (datetime.utcnow() - timedelta(days=7)).isoformat(timespec="seconds") + "Z"

        params = {
            "filter": f"creationdate:[{start_time}..]",
            "limit": limit
        }

        while True:
            params["offset"] = offset
            response = requests.get(base_url, headers=HEADERS, params=params)
            if response.status_code == 200:
                data = response.json()

                if "orders" not in data:
                    break

                orders = data["orders"]
                all_orders.extend(orders)
                if len(orders) < limit:
                    break

                offset += limit

            else:
                try:
                    err = response.json()
                    if err.get("errors") and err["errors"][0].get("errorId") == 1001:
                        access_token = eb.refresh_access_token(userid, "Ebay")
                        get_product_ordered_from_background(userid, enroll_id)
                except Exception:
                    return "Error"
            
        return all_orders

    except Exception as e:
        print(f"[EXCEPTION] Could not fetch ordered items from eBay: {e}")
        return "Error"


    
    # try:
    #     url = "https://api.ebay.com/sell/fulfillment/v1/order"
    #     headers = {
    #         "Authorization": f"Bearer {access_token}",
    #         "Content-Type": "application/json"
    #     }
    #     orders = []
    #     offset = 0
    #     limit = 50  # Adjust the limit as needed
        
    #     while True:
    #         params = {
    #             "limit": limit,
    #             "offset": offset
    #         }
            
    #         response = requests.get(url, headers=headers, params=params)
            
    #         if response.status_code == 200:
    #             data = response.json()
    #             orders.extend(data.get('orders', []))
                
    #             if len(data.get('orders', [])) < limit:
    #                 break  # No more orders to fetch
    #             offset += limit
    #         else:
    #             print(f"Failed to retrieve orders: {response.text}")
        
    #     return orders   
    # except Exception as e:
    #     print(f'Could not fetch ordered items from ebay Error: {e}')
    #     return None
        

# Function to get details of specific item ordered on ebay
# Limit to 5 calls per second (eBay's typical limit)
@sleep_and_retry
@limits(calls=5, period=1)
def get_item_ordered_details(enroll_id, item_id):
    # Get access_token
    try:
        user_data = MarketplaceEnronment.objects.get(_id=enroll_id, marketplace_name="Ebay")  # requests.get(f"https://service.swiftsuite.app/marketplaceApp/get_refresh_access_token/{user.id}/Ebay")
    except Exception as e:
        print(f"Failed to fetch access token")
        return None
    
    access_token =  user_data.access_token
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
        return get_item_ordered_details(enroll_id, item_id)
        
    product_data = response.json()
    if response.status_code == 200:
        return product_data
    else:
        print(f"Failed to retrieve details for Item ID {item_id}: {response.text}")
        return None
        

# --- GET ALL WOOCOMMERCE ORDERS ---
def get_all_woocommerce_orders(userid):
    enrollment = MarketplaceEnronment.objects.get(user_id=userid, marketplace_name="Woocommerce")
    # Set up the WooCommerce API client
    wcapi = API(
        url = enrollment.wc_consumer_url, 
        consumer_key = enrollment.wc_consumer_key,  
        consumer_secret = enrollment.wc_consumer_secret, 
        version = "wc/v3",
        timeout=30
    )

    page = 1
    all_orders = []

    while True:
        response = wcapi.get("orders", params={"per_page": 100, "page": page})

        if response.status_code != 200:
            print("Error fetching orders:", response.json())
            return []

        orders = response.json()

        if not orders:  # no more pages
            break

        all_orders.extend(orders)
        page += 1

    return all_orders


# Update orders on ebay to the one on local database at the background
# @api_view(["GET"])
def sync_ebay_order_with_local():

    user_token = MarketplaceEnronment.objects.all() # get all user to get their access_token and user id
    for user in user_token:
        if user.marketplace_name == "Ebay":    
            # Fetch all orders from eBay
            ebay_orders = get_product_ordered_from_background(user.user_id, user._id)
            if ebay_orders == None:
                # Refresh access token and retry fetching orders
                print(f"Access token expired for user {user.user_id}, refreshing token.")
                continue
            elif ebay_orders == "Error":
                print(f"Failed to fetch all orders from ebay for user {user.user_id}.")
                continue
            else:
                for order in ebay_orders:
                    # Check if order already exists on local database else insert it
                    try:
                        lineItems = order.get('lineItems', [])[0]
                        ebay_order_id = order.get("orderId")
                        exist_order = OrdersOnEbayModel.objects.get(orderId=ebay_order_id)
                        product_data = InventoryModel.objects.all().filter(market_item_id=lineItems.get("legacyItemId"))
                        if len(product_data) == 0:
                            product_data = {"vendor_name":"Not Found"}
                        else:
                            product_data = product_data.values()[0]
                        OrdersOnEbayModel.objects.filter(orderId=ebay_order_id).update(orderFulfillmentStatus=order.get("orderFulfillmentStatus"), orderPaymentStatus=order.get("orderPaymentStatus"), vendor_name=product_data.get('vendor_name'))
                    except:
                        try:
                            lineItems = order.get('lineItems', [])[0]
                            product_data = InventoryModel.objects.all().filter(market_item_id=lineItems.get("legacyItemId"))
                            if len(product_data) == 0:
                                print(f"product details returned None in orderApp for item with item_id: {lineItems.get('legacyItemId')}")
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
                                                        marketItemId=product_data.get("market_item_id"), localizeAspects=product_data.get("item_specific_fields"), vendor_name=product_data.get('vendor_name'), market_name="Ebay")
                            
                            save_order.save()
                        except Exception as e:
                            print(f"Ordered item insert error {e} ")
                            continue
            
        elif user.marketplace_name == "WooCommerce":
            woocommerce_orders = get_all_woocommerce_orders(user.user_id)
            for order in woocommerce_orders:
                try:
                    wc_order_id = order.get("id")
                    exist_order = OrdersOnEbayModel.objects.get(orderId=wc_order_id)
                    product_data = InventoryModel.objects.all().filter(market_item_id=order.get("id"))
                    if len(product_data) == 0:
                        product_data = {"vendor_name":""}
                    else:
                        product_data = product_data.values()[0]
                    OrdersOnEbayModel.objects.filter(orderId=wc_order_id).update(orderFulfillmentStatus=order.get("status"), orderPaymentStatus=order.get("payment_method_title"), vendor_name=product_data.get('vendor_name'), market_name="WooCommerce")
                except:
                    try:
                        product_data = InventoryModel.objects.all().filter(market_item_id=order.get("id"))
                        if len(product_data) == 0:
                            product_data = {"vendor_name":""}
                        else:
                            product_data = product_data.values()[0]
                        save_order = OrdersOnEbayModel(user_id=user.user_id, orderId=order.get("id"),
                                                    creationDate=order.get("date_created"),
                                                    orderFulfillmentStatus=order.get("status"), orderPaymentStatus=order.get("payment_method_title"),
                                                    sku=order.get("sku"), title=order.get("name"),
                                                    quantity=order.get("quantity"),
                                                    marketItemId=product_data.get("market_item_id"), image=product_data.get("picture_detail"),
                                                    additionalImages=product_data.get("thumbnailImage"), description=product_data.get("description"), categoryId=product_data.get("category_id"),
                                                    localizeAspects=product_data.get("item_specific_fields"), vendor_name=product_data.get('vendor_name'))
                        save_order.save()
                    except Exception as e:
                        print(f"WooCommerce Ordered item insert error {e} ")
                        continue
                

# function to manually sync orders for a specific user
def manual_sync_order_with_local(userid):
    user_token = MarketplaceEnronment.objects.filter(user_id=userid) # get all account accosiated with the user to get their access_token and user id
    for user in user_token:
        if user.marketplace_name == "Ebay":    
            # Fetch all orders from eBay
            ebay_orders = get_product_ordered_from_background(user.user_id, user._id)
            if ebay_orders == None:
                # Refresh access token and retry fetching orders
                print(f"Access token expired for user {user.user_id}, refreshing token.")
                continue
            elif ebay_orders == "Error":
                print(f"Failed to fetch all orders from ebay for user {user.user_id}.")
                continue
            else:
                for order in ebay_orders:
                    # Check if order already exists on local database else insert it
                    try:
                        lineItems = order.get('lineItems', [])[0]
                        ebay_order_id = order.get("orderId")
                        exist_order = OrdersOnEbayModel.objects.get(orderId=ebay_order_id)
                        product_data = InventoryModel.objects.all().filter(market_item_id=lineItems.get("legacyItemId"))
                        if len(product_data) == 0:
                            product_data = {"vendor_name":"Not Found"}
                        else:
                            product_data = product_data.values()[0]
                        OrdersOnEbayModel.objects.filter(orderId=ebay_order_id).update(orderFulfillmentStatus=order.get("orderFulfillmentStatus"), orderPaymentStatus=order.get("orderPaymentStatus"), vendor_name=product_data.get('vendor_name'))
                    except:
                        try:
                            lineItems = order.get('lineItems', [])[0]
                            product_data = InventoryModel.objects.all().filter(market_item_id=lineItems.get("legacyItemId"))
                            if len(product_data) == 0:
                                print(f"product details returned None in orderApp for item with item_id: {lineItems.get('legacyItemId')}")
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
                                                        marketItemId=product_data.get("market_item_id"), localizeAspects=product_data.get("item_specific_fields"), vendor_name=product_data.get('vendor_name'), market_name="Ebay")
                            
                            save_order.save()
                        except Exception as e:
                            print(f"Ordered item insert error {e} ")
                            continue
            
        elif user.marketplace_name == "WooCommerce":
            woocommerce_orders = get_all_woocommerce_orders(user.user_id)
            for order in woocommerce_orders:
                try:
                    wc_order_id = order.get("id")
                    exist_order = OrdersOnEbayModel.objects.get(orderId=wc_order_id)
                    product_data = InventoryModel.objects.all().filter(market_item_id=order.get("id"))
                    if len(product_data) == 0:
                        product_data = {"vendor_name":""}
                    else:
                        product_data = product_data.values()[0]
                    OrdersOnEbayModel.objects.filter(orderId=wc_order_id).update(orderFulfillmentStatus=order.get("status"), orderPaymentStatus=order.get("payment_method_title"), vendor_name=product_data.get('vendor_name'), market_name="WooCommerce")
                except:
                    try:
                        product_data = InventoryModel.objects.all().filter(market_item_id=order.get("id"))
                        if len(product_data) == 0:
                            product_data = {"vendor_name":""}
                        else:
                            product_data = product_data.values()[0]
                        save_order = OrdersOnEbayModel(user_id=user.user_id, orderId=order.get("id"),
                                                    creationDate=order.get("date_created"),
                                                    orderFulfillmentStatus=order.get("status"), orderPaymentStatus=order.get("payment_method_title"),
                                                    sku=order.get("sku"), title=order.get("name"),
                                                    quantity=order.get("quantity"),
                                                    marketItemId=product_data.get("market_item_id"), image=product_data.get("picture_detail"),
                                                    additionalImages=product_data.get("thumbnailImage"), description=product_data.get("description"), categoryId=product_data.get("category_id"),
                                                    localizeAspects=product_data.get("item_specific_fields"), vendor_name=product_data.get('vendor_name'))
                        save_order.save()
                    except Exception as e:
                        print(f"WooCommerce Ordered item insert error {e} ")
                        continue



def get_ebay_order_details(user_id, market_name, ebay_order_id):
    env = MarketplaceEnronment.objects.filter(
        user_id=user_id,
        marketplace_name__iexact=market_name
    ).first()

    if not env:
        raise ValueError(
            f"Marketplace environment not found for {market_name}-{user_id}-{ebay_order_id}"
        )

    enroll_id = env._id
    
    access_token = MarketplaceEnronment.objects.get(_id=enroll_id, marketplace_name="Ebay").access_token
    
    url = f'https://api.ebay.com/sell/fulfillment/v1/order/{ebay_order_id}'

    # Set up the headers with the access token
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    try:
        response = requests.get(url, headers=headers)
        order_details = response.json()
        
        return order_details
        
    except Exception as e:
        print(f"Error fetching ebay order details: {e}")
        return None
    
    
    
def create_vendor_order_log(order: OrdersOnEbayModel):
    
    if VendorOrderLog.objects.filter(
        order=order,
        vendor=order.vendor_name,
    ).exclude(status=VendorOrderLog.VendorOrderStatus.FAILED).exists():
        return

    enrollment = get_vendor_enrollment(order.marketItemId)
    if not enrollment:
        logger.error(f"Enrollment not found for order with marketItemId {order.marketItemId}.")
        return
    
    order_log = VendorOrderLog.objects.create(
        order=order,
        enrollment=enrollment,
        vendor=order.vendor_name,
        status=VendorOrderLog.VendorOrderStatus.CREATED,
    )
    
    return order_log  


def get_vendor_enrollment(marketItemId):
    # get item on inventory using the marketItemId
    inventory = InventoryModel.objects.filter(
        market_item_id=marketItemId
    ).first()
    if not inventory:
        logger.error(f"Inventory item with marketItemId {marketItemId} not found in inventory.")
        
    if not inventory.product:
        logger.error(
            f"Inventory {inventory.id} has no linked product"
        )
        return None

    if not inventory.product.enrollment:
        logger.error(
            f"Product {inventory.product.id} has no enrollment"
        )
        return None

    return inventory.product.enrollment