import requests, time
from marketplaceApp.models import MarketplaceEnronment
from ratelimit import limits, sleep_and_retry
from .models import OrdersOnEbayModel
from inventoryApp.models import InventoryModel
from datetime import datetime, timedelta
from woocommerce import API
from .models import VendorOrderLog
from rest_framework.response import Response
from rest_framework import status
import base64
import requests
from decouple import config
from django.db import transaction
from django.utils import timezone
import threading
import logging
logger = logging.getLogger(__name__)



# Function to refresh the access token using the refresh token
def background_refresh_access_token():
    client_id = config("EB_CLIENT_ID")
    client_secret = config("EB_CLIENT_SECRET")
    token_url = "https://api.ebay.com/identity/v1/oauth2/token"
    scopes = [
            "https://api.ebay.com/oauth/api_scope",
            "https://api.ebay.com/oauth/api_scope/sell.marketing.readonly",
            "https://api.ebay.com/oauth/api_scope/sell.marketing",
            "https://api.ebay.com/oauth/api_scope/sell.inventory.readonly",
            "https://api.ebay.com/oauth/api_scope/sell.inventory",
            "https://api.ebay.com/oauth/api_scope/sell.account.readonly",
            "https://api.ebay.com/oauth/api_scope/sell.account",
            "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly",
            "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
            "https://api.ebay.com/oauth/api_scope/sell.analytics.readonly",
            "https://api.ebay.com/oauth/api_scope/sell.finances",
            "https://api.ebay.com/oauth/api_scope/sell.payment.dispute",
            "https://api.ebay.com/oauth/api_scope/commerce.identity.readonly",
            "https://api.ebay.com/oauth/api_scope/sell.reputation",
            "https://api.ebay.com/oauth/api_scope/sell.reputation.readonly",
            "https://api.ebay.com/oauth/api_scope/commerce.notification.subscription",
            "https://api.ebay.com/oauth/api_scope/commerce.notification.subscription.readonly",
            "https://api.ebay.com/oauth/api_scope/sell.stores",
            "https://api.ebay.com/oauth/api_scope/sell.stores.readonly"
        ]
    while True:
        try:
            user_data = MarketplaceEnronment.objects.filter(marketplace_name="Ebay")
        except Exception as e:
            return Response(f"Failed to fetch user data {e}", status=status.HTTP_400_BAD_REQUEST)
        for user in user_data:
            access_token = user.access_token
            refresh_token = user.refresh_token

        credentials = f"{client_id}:{client_secret}"
        credentials_base64 = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {credentials_base64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        body = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": " ".join(scopes)  # Ensure scope is passed correctly
        }

        response = requests.post(token_url, headers=headers, data=body)
        if response.status_code != 200:
            return Response(f"Failed to refresh access token. Authorization code has expired", status=status.HTTP_400_BAD_REQUEST)

        result = response.json()
        access_token = result.get('access_token')
        
        if not access_token:
            return Response(f"Failed to get access token from response", status=status.HTTP_400_BAD_REQUEST)

        MarketplaceEnronment.objects.filter(user_id=user.user_id, marketplace_name="Ebay").update(access_token=access_token, refresh_token=refresh_token)
        logger.info(f"Successfully refreshed access token with access_token: {access_token}")
        time.sleep(12 * 60)  # Sleep for 12 minutes before refreshing again (eBay tokens typically last for 10 minutes)

threading.Thread(target=background_refresh_access_token, daemon=True).start()  # Start the token refresh in a background thread


# Function to retrieve all fulfilment orders from Ebay
def get_product_ordered_from_background(userid, enroll_id):
    # Get access_token
    try:
        user_data = MarketplaceEnronment.objects.get(_id=enroll_id, marketplace_name="Ebay")
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
            if ebay_orders == "Error":
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
    with transaction.atomic():
        # Lock the order to serialize attempts for this specific order
        _ = OrdersOnEbayModel.objects.select_for_update().get(pk=order.pk)

        # Check for ANY existing log for this order+vendor
        existing_log = VendorOrderLog.objects.filter(
            order=order,
            vendor=order.vendor_name,
        ).first()

        if existing_log:
           return existing_log

        # Logic to create new if strictly not exists
        enrollment = get_vendor_enrollment(order.marketItemId)
        if not enrollment:
            logger.error(f"Enrollment not found for order-{order.orderId} with marketItemId {order.marketItemId}.")
            return None
        
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


def get_order_details_by_order_id(user_id, market_name, order_id):

    from marketplaceApp.views import Ebay
    ebay = Ebay()
    
    # Get access_token
    access_token = ebay.refresh_access_token(user_id, market_name)
    
    EBAY_ORDER_DETAILS_URL = f"https://api.ebay.com/sell/fulfillment/v1/order/{order_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    response = requests.get(EBAY_ORDER_DETAILS_URL, headers=headers)
    
    if response.status_code == 200:
        order_details = response.json()
        return order_details
    else:
        logger.error(
            f"eBay order details failed | "
            f"status={response.status_code} | body={response.text}"
        )
        return None


def push_tracking_to_ebay(vendor_order_log: VendorOrderLog):
    """
    Push tracking information from a VendorOrderLog to eBay.
    Updates the local OrdersOnEbayModel status upon success.
    """
    logger.info(f"Preparing to push tracking for order {vendor_order_log.order.orderId}")
    
    user_id = vendor_order_log.enrollment.user.id
    ebay_order_id = vendor_order_log.order.orderId
    
    # Get Ebay credentials
    env = MarketplaceEnronment.objects.filter(
        user_id=user_id,
        marketplace_name="Ebay"
    ).first()
    
    if not env:
        logger.error(f"No Ebay environment found for user {user_id}")
        return False
        
    access_token = env.access_token
    order_details = get_order_details_by_order_id(user_id, "Ebay", ebay_order_id)
    if not order_details:
        logger.error(f"Failed to get order details for order {ebay_order_id}")
        return False

    line_item_id = order_details['lineItems'][0]['lineItemId']
    if not line_item_id:
        logger.error(f"Failed to get line item id for order {ebay_order_id}")
        return False


    url = f'https://api.ebay.com/sell/fulfillment/v1/order/{ebay_order_id}/shipping_fulfillment'

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }

    if (
        not vendor_order_log.shipped_at
        or not vendor_order_log.tracking_number
        or not vendor_order_log.carrier
    ):
        logger.info(
            f"Skipping eBay tracking push for order "
            f"{vendor_order_log.reference_id}: "
            f"shipment not complete"
        )
        return False
        
    payload = {
        "shippedDate": vendor_order_log.shipped_at.isoformat(),
        "shippingCarrierCode": vendor_order_log.carrier,
        "trackingNumber": vendor_order_log.tracking_number,
        "lineItems": [
            {
                "lineItemId": line_item_id
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code in [200, 201, 204]:
            logger.info(f"Successfully pushed tracking to eBay for order {ebay_order_id}")
            
            # Update local eBay order record
            OrdersOnEbayModel.objects.filter(
                orderId=vendor_order_log.order.orderId
            ).update(
                tracking_id=vendor_order_log.tracking_number,
                orderFulfillmentStatus="SHIPPED",
            )
            vendor_order_log.status = VendorOrderLog.VendorOrderStatus.DELIVERED
            vendor_order_log.delivered_at = timezone.now()
            vendor_order_log.save()
            return response.json()
            
        else:
            logger.error(
                f"Failed to push tracking to eBay. Status: {response.status_code}, "
                f"Response: {response.text}"
            )
            return False
            
    except Exception as e:
        logger.error(f"Exception pushing tracking to eBay for order {ebay_order_id}: {e}")
        return False