import json
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from marketplaceApp.views import Ebay
from .serializers import CancelOrderModelSerializer
from .models import OrdersOnEbayModel
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from inventoryApp.models import InventoryModel
from .tasks import sync_ebay_order_task
from accounts.permissions import IsOwnerOrHasPermission
from vendorEnrollment.utils import with_module


# Create your views here.
class OrderEbay:
    
    def __init__(self):
        super().__init__()
    

    # Function to retrieve all fulfilment orders from Ebay
    @with_module('orders')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_product_ordered(request, userid, page_number, num_per_page):
        try:
            # check if user is subaccount
            user = request.user
            if user:
                if user.parent_id:
                    userid = user.parent_id

            order_items = OrdersOnEbayModel.objects.all().filter(user_id=userid).values().order_by('creationDate').reverse()
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
            return Response(f"Failed to get ordered items.: {e}", status=status.HTTP_400_BAD_REQUEST)
        

    # Crease a function to get order item full details using item ID
    def get_product_details_by_item_id(self, access_token, item_id):
        EBAY_ITEM_DETAILS_URL = f"https://api.ebay.com/buy/browse/v1/item/get_item_by_legacy_id?legacy_item_id={item_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        response = requests.get(EBAY_ITEM_DETAILS_URL, headers=headers)
        
        if response.status_code == 200:
            item_details = response.json()
            return item_details
        else:
            return None


    # Function to get ordered details of an item
    @with_module('orders')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_ordered_item_details(request, userid, market_name, ebayorderid):
        # check if user is subaccount
        user = request.user
        if user:
            if user.parent_id:
                userid = user.parent_id

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
            product_data = InventoryModel.objects.all().filter(market_item_id=items.get("legacyItemId")).values()
            
            return JsonResponse({"ordered_details":order_details, "product_data":list(product_data)}, safe=False, status=status.HTTP_200_OK)
        except requests.exceptions.HTTPError as err:
            return Response(f"Connection error occurred", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(f"An error occurred, contact support team", status=status.HTTP_400_BAD_REQUEST)


    # Function to cancel an order from ebay
    @with_module('orders')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['POST'])
    def cancel_order_from_ebay(request, userid, market_name, ebayorderid):
        # check if user is subaccount
        user = request.user
        if user:
            if user.parent_id:
                userid = user.parent_id
                
        # Get access_token
        access_token = Ebay.refresh_access_token(request, userid, market_name)
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
            return Response(f"Connection error occurred.", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(f"An error occurred, contact support team.", status=status.HTTP_400_BAD_REQUEST)


    # Function to track order and update fulfilment status on Ebay
    def track_order_on_ebay(self, userid, ebayorderid, tracking_number, carrier_code, line_item_id, shipped_date):
                
        # Get access_token
        access_token = Ebay.refresh_access_token(userid, "Ebay")
        url = f'https://api.ebay.com/sell/fulfillment/v1/order/{ebayorderid}/shipping_fulfillment'

        # Set up the headers with the access token
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }
        
        # Define the tracking details payload
        payload = {
            "shippedDate": shipped_date,
            "shippingCarrierCode": carrier_code,    # (UPS, USPS, FedEx, DHL, Royal Mail, Hermes, etc.)
            "trackingNumber": tracking_number,
            "lineItems": [
                {
                    "lineItemId": line_item_id
                }
            ]
        }
        
        try:
            response = requests.post(url, headers=headers, json=json.dumps(payload))
            if response.status_code in [200, 201, 204]:
                tracking_details = response.json()
                return tracking_details
            else:
                print(f"Failed to update tracking on eBay. Status code: {response.status_code}, Response: {response.text}")
                return None
        except requests.exceptions.HTTPError as err:
            print(f"Connection error occurred: {err}")
            return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None


    
    
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