from django.shortcuts import render, redirect, get_object_or_404
import requests, threading, time, base64
from urllib.parse import urlencode, urlparse, parse_qs
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.csrf import csrf_exempt
from ebaysdk.trading import Connection as Trading
from marketplaceApp.views import Ebay
from .serializers import CancelOrderModelSerializer
from .models import CancelOrderModel, OrdersOnEbayModel
from accounts.models import User
from vendorEnrollment.models import CwrUpdate, FragrancexUpdate, LipseyUpdate, RsrUpdate, SsiUpdate, ZandersUpdate, Generalproducttable
from marketplaceApp.models import MarketplaceEnronment
from ratelimit import limits, sleep_and_retry
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


# Create your views here.

class OrderEbay(APIView):
    # permission_classes = [IsAuthenticated]
    def __init__(self):
        super().__init__()
    
    # Function to refresh the access token using the refresh token
    def refresh_access_token_for_sync(userid, market_name):
        eb = Ebay()
        try:
            connection = MarketplaceEnronment.objects.all().get(user_id=userid, marketplace_name=market_name)
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

        MarketplaceEnronment.objects.filter(user_id=userid, marketplace_name=market_name).update(access_token=access_token, refresh_token=refresh_token)
        return access_token

    # Function to retrieve all fulfilment orders from Ebay
    @api_view(['GET'])
    def get_product_ordered(request, userid, page_number, num_per_page):
        try:
            order_items = OrdersOnEbayModel.objects.all().filter(user_id=userid).values().order_by('_id')
            page = request.GET.get('page', int(page_number))
            paginator = Paginator(order_items, int(num_per_page))
            try:
                order_items_objects = paginator.page(page)
            except PageNotAnInteger:
                order_items_objects = paginator.page(1)
            except EmptyPage:
                order_items_objects = paginator.page(paginator.num_pages)
            
            return JsonResponse({"Total_count":len(order_items), "Total_pages":paginator.num_pages, "order_items":list(order_items_objects)}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get ordered items: {e}", status=status.HTTP_400_BAD_REQUEST)
            
        # # Get access_token
        # access_token = Ebay.refresh_access_token(request, userid, market_name)
    
        # # Set eBay API endpoint and headers
        # url = "https://api.ebay.com/sell/fulfillment/v1/order"
        # headers = {
        #     "Authorization": f"Bearer {access_token}",
        #     "Content-Type": "application/json"
        # }
        # orders = []
        # offset = 0
        # limit = 50  # Adjust the limit as needed
        
        # while True:
        #     params = {
        #         "limit": limit,
        #         "offset": offset
        #     }
            
        #     response = requests.get(url, headers=headers, params=params)
            
        #     if response.status_code == 200:
        #         data = response.json()
        #         orders.extend(data.get('orders', []))
                
        #         if len(data.get('orders', [])) < limit:
        #             break  # No more orders to fetch
        #         offset += limit
        #     else:
        #         return Response(f"Failed to retrieve orders: {response.text}", status=status.HTTP_400_BAD_REQUEST)
            
        # return JsonResponse({"total ordered":len(orders), "order_items":orders}, safe=False, status=status.HTTP_200_OK)   

    
    # Create a function to get details of product ordered by item legacy id
    def get_product_details_by_item_id(self, access_token, item_id):
        url = f"https://api.ebay.com/buy/browse/v1/item/get_item_by_legacy_id?legacy_item_id={item_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            product_data = response.json()
            remove_keys = ["sellerItemRevision", "price", "categoryPath", "categoryIdPath", "gtin", "estimatedAvailabilities", "shippingOptions", "shipToLocations", "returnTerms", "taxes", "localizedAspects", "topRatedBuyingExperience", "paymentMethods"]
            list(map(product_data.pop, remove_keys))

            return product_data
        else:
            return Response(f"error: {response.text}")

    # Function to get ordered details of an item
    @api_view(['GET'])
    def get_ordered_item_details(request, userid, market_name, ebayorderid):
        eb = OrderEbay()
        # Get access_token
        access_token = Ebay.refresh_access_token(request, userid, market_name)
        
        url = f'https://api.ebay.com/sell/fulfillment/v1/order/{ebayorderid}'

        # Set up the headers with the access token
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }
        try:
            response = requests.get(url, headers=headers)
            order_details = response.json()
            
            # Get details of product ordered using item legacy id
            items = order_details.get('lineItems', [])[0]
            product_data = eb.get_product_details_by_item_id(access_token, items.get('legacyItemId'))
            
            return JsonResponse({"ordered_details":order_details}, safe=False, status=status.HTTP_200_OK) #, "product_data":product_data
        except requests.exceptions.HTTPError as err:
            return Response(f"HTTP error occurred: {err}", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(f"An error occurred: {e}", status=status.HTTP_400_BAD_REQUEST)

    # Function to cancel an order from ebay
    @api_view(['POST'])
    def cancel_order_from_ebay(request, userid, market_name, ebayorderid):
        valid_choices_fields
        url = f'https://api.ebay.com/post-order/v2/cancellation/{ebayorderid}'

        # Set up the headers with the access token
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }
        # Validate the serializer
        serializer = CancelOrderModelSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        cancel_reason = serializer.validated_data["cancel_reason"]
        # Define the cancellation request payload
        payload = {
            "cancelReason": cancel_reason,  # Specify the reason for cancellation
            "orderId": ebayorderid
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            cancellation_details = response.json()
            return JsonResponse(cancellation_details, safe=False, status=status.HTTP_200_OK)
        except requests.exceptions.HTTPError as err:
            return Response(f"HTTP error occurred: {err}", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(f"An error occurred: {e}", status=status.HTTP_400_BAD_REQUEST)
            
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
            return OrderEbay.get_item_ordered_details(access_token, item_id)
            
        product_data = response.json()
        if response.status_code == 200:
            return product_data
        else:
            print(f"Failed to retrieve details for Item ID {item_id}: {response.text}")
            return None
            
            
    # Update orders on ebay to the one on local database at the background
    # @api_view(["GET"])
    def sync_ebay_order_with_local():
        print("synchronizing ebay order starts")
        while True:
            # time.sleep(1800)
            vendor_name_item = ""
            print("synchronizing ebay order starts inside the while loop")
            user_token = User.objects.all() #get all user to get their access_token and user id
            for user in user_token:
                # Get access_token
                access_token = OrderEbay.refresh_access_token_for_sync(user.id, "Ebay") #requests.get(f"https://service.swiftsuite.app/marketplaceApp/get_refresh_access_token/{user.id}/Ebay")
                if not access_token:
                    print(f"Failed to refresh access token. Access token returns none in orderapp")
                    continue
                    
                # Fetch all orders from eBay
                ebay_orders = OrderEbay.get_product_ordered_from_background(access_token)
                if ebay_orders == None:
                    print(f"Failed to fetch ordered items from ebay for user {user.id}")
                    continue
                
                for order in ebay_orders:
                    # Check if order already exists on local database else insert it
                    try:
                        ebay_order_id = order.get("orderId")
                        exist_order = OrdersOnEbayModel.objects.get(orderId=ebay_order_id)
                        OrdersOnEbayModel.objects.filter(orderId=ebay_order_id).update(orderFulfillmentStatus=order.get("orderFulfillmentStatus"), orderPaymentStatus=order.get("orderPaymentStatus"))
                    except:
                        db_item = ""
                        lineItems = order.get('lineItems', [])[0]
                        product_data = OrderEbay.get_item_ordered_details(access_token, lineItems.get('legacyItemId'))
                        if product_data == None:
                            print(f"product details returned None in orderApp for item with item_id {order.get('ebay_item_id')}")
                            continue
                        print('trying to insert data to the database')

                        # Get the product vendor name from the local database.
                        vendor_list = ["CwrUpdate", "FragrancexUpdate", "LipseyUpdate", "RsrUpdate", "SsiUpdate", "ZandersUpdate"]
                        for vendor_db in vendor_list:
                            try:
                                # Get the actual model class from the string name
                                model_class = globals()[vendor_db]
                                db_item = model_class.objects.get(sku=product_data.get("sku"))
                                vendor_name_item = vendor_db.split("Up")[0]
                                break
                            except Exception as ea:
                                print(f"product do not match any vendor in orderApp. Error is: {ea}")
                                vendor_name_item = ""
                                continue
                        if db_item:
                            OrdersOnEbayModel.objects.filter(orderId=order.get("orderId")).update(vendor_name=vendor_name_item)
                        else:
                            save_order = OrdersOnEbayModel(user_id=user.id, orderId=order.get("orderId"),
                                                        legacyOrderId=order.get("legacyOrderId"), creationDate=order.get("creationDate"),
                                                        orderFulfillmentStatus=order.get("orderFulfillmentStatus"), orderPaymentStatus=order.get("orderPaymentStatus"),
                                                        sellerId=order.get("sellerId"), buyer=order.get("buyer"), cancelStatus=order.get("cancelStatus"),
                                                        pricingSummary=order.get("pricingSummary"), paymentSummary=order.get("paymentSummary"), 
                                                        fulfillmentStartInstructions=order.get("fulfillmentStartInstructions"), sku=lineItems.get("sku"), title=lineItems.get("title"),
                                                        lineItemCost=lineItems.get("lineItemCost"), quantity=lineItems.get("quantity"),
                                                        listingMarketplaceId=lineItems.get("listingMarketplaceId"), purchaseMarketplaceId=lineItems.get("purchaseMarketplaceId"),
                                                        itemLocation=lineItems.get("itemLocation"), legacyItemId=lineItems.get('legacyItemId'), image=product_data.get("image"),
                                                        additionalImages=product_data.get("additionalImages"), mpn=product_data.get("mpn"),
                                                        description=product_data.get("description"), categoryId=product_data.get("categoryId"),
                                                        vendor_name=vendor_name_item, ebayItemId=product_data.get("itemId"), localizeAspects=product_data.get("localizeAspects"))
                            save_order.save()
            print("All user's order update were successful")

# Create a code to perform ebay local order sync process at the background
order_sync_thread = threading.Thread(target=OrderEbay.sync_ebay_order_with_local, name='ebay_swift_order_sync', daemon=True)
# order_sync_thread.start()


class Woocommerce(APIView):
    pass


class Amazon(APIView):
    pass


class Shopify(APIView):
    pass


class Walmart(APIView):
    pass


class Woo2(APIView):
    pass