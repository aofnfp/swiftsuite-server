import json
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from marketplaceApp.views import Ebay
from .serializers import CancelOrderModelSerializer, OrderSyncSerializer
from .models import OrdersOnEbayModel
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from inventoryApp.models import InventoryModel
from accounts.permissions import IsOwnerOrHasPermission
from vendorEnrollment.utils import with_module
from .tasks import manual_sync_order_with_local_task
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from vendorEnrollment.pagination import CustomOffsetPagination
from .models import VendorOrderLog
from .order_clients.rsr_order import RsrOrderApiClient
from .order_clients.fx_order import FrgxOrderApiClient
from .utils import push_tracking_to_ebay, get_access_token


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


    # Create function to manually sync ebay orders with local db
    @with_module('orders')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def sync_ebay_order_with_local_manually(request, userid):
        # check if user is subaccount
        user = request.user
        if user:
            if user.parent_id:
                userid = user.parent_id
        try:
            manual_sync_order_with_local_task.delay(userid)
            return Response("Orders sync task has been initiated.", status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to initiate sync task: {e}", status=status.HTTP_400_BAD_REQUEST)

    
    
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


class OrderSyncView(viewsets.ReadOnlyModelViewSet):
    queryset = (
        OrdersOnEbayModel.objects
        .prefetch_related("vendor_orders")
        .order_by("-creationDate")
    )

    module_name = 'orders'
    serializer_class = OrderSyncSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrHasPermission]
    pagination_class = CustomOffsetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_fields = {
        'orderId': ['exact', 'icontains'],
        'creationDate': ['gte', 'lte'],
        'vendor_name': ['exact'],
        'market_name': ['exact'],
        'orderFulfillmentStatus': ['exact'],
        'vendor_orders__status': ['exact'],
    }


    search_fields = ['orderId', 'creationDate', 'vendor_name', 'market_name', 'orderFulfillmentStatus', 'vendor_orders__status']

    ordering_fields = ['orderId', 'creationDate', 'vendor_name', 'market_name', 'vendor_orders__status']
    
   
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # check if user is subaccount
        user = self.request.user
        if user:
            if user.parent_id:
                userid = user.parent_id
            else:
                userid = user.id
        
        vendor_status = self.request.query_params.get('vendor_status', None)
        if vendor_status:
            queryset = queryset.filter(vendor_orders__status=vendor_status)

        return queryset.filter(user=userid)


class PlaceOrderView(APIView):
    module_name = 'orders'
    permission_classes = [IsAuthenticated, IsOwnerOrHasPermission]

    def post(self, request, market_name, order_id):
        user = request.user
        if user and user.parent_id:
            user = user.parent
        
        
        VendorOrder = VendorOrderLog.objects.filter(
            order__orderId=order_id,
            order__market_name__iexact=market_name,
            enrollment__user=user,
        ).first()

        if not VendorOrder:
            order = OrdersOnEbayModel.objects.filter(
                orderId=order_id,
                market_name__iexact=market_name,
                user=user
            ).first()
            
            if not order:
                return Response(
                    {"message": "Vendor order log not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            from .utils import get_vendor_enrollment
            enrollment = get_vendor_enrollment(order.marketItemId)
            if not enrollment:
                return Response(
                    {
                        "message": "Product is not linked to any active vendor enrollment.",
                        "order_id": order_id,
                        "market_item_id": order.marketItemId,
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            VendorOrder = VendorOrderLog.objects.create(
                order=order,
                enrollment=enrollment,
                vendor= order.vendor_name,
                status=VendorOrderLog.VendorOrderStatus.CREATED
            )
        
        elif VendorOrder.status in [
            VendorOrderLog.VendorOrderStatus.PROCESSING,
            VendorOrderLog.VendorOrderStatus.SHIPPED,
            VendorOrderLog.VendorOrderStatus.DELIVERED,
        ]:
            return Response(
                {"message": f"Order is already placed with {VendorOrder.vendor}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if VendorOrder.vendor.lower() == "fragrancex":
            # Initialize client
            order_client = FrgxOrderApiClient(VendorOrder)
            ordered_details = order_client.get_order_details()  
            # Define bulk order payload
            bulk_order = order_client.build_bulk_payload(ordered_details)
            # Place the order
            result = order_client.place_bulk_order(bulk_order)
        
            if result.get("Message", False) and result.get("BulkOrderId", False):
                VendorOrder.status = VendorOrderLog.VendorOrderStatus.PROCESSING
                VendorOrder.vendor_order_id = result.get("BulkOrderId")
                VendorOrder.raw_response = result
                VendorOrder.save()
                return Response(
                    {"message": "Order placed successfully.", "data": result, "order_info": bulk_order},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"message": "Failed to place order.", "data": result, "order_info": bulk_order},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        
        elif VendorOrder.vendor.lower() == "rsr":
            # Initialize RSR client
            rsr_client = RsrOrderApiClient(VendorOrder)
            order_details = rsr_client.get_order_details()
            payload = rsr_client.build_payload(order_details)
            result = rsr_client.place_order(payload)
            
            
            if result.get("StatusCode") == "00":
                VendorOrder.status = VendorOrderLog.VendorOrderStatus.PROCESSING
                VendorOrder.vendor_order_id = (
                    result.get("ConfirmResp") or result.get("WebRef")
                )
                VendorOrder.raw_response = result
                VendorOrder.save()
                
                return Response(
                    {"message": "RSR order placed successfully", "data": result},
                    status=status.HTTP_200_OK
                )

            VendorOrder.status = VendorOrderLog.VendorOrderStatus.FAILED
            VendorOrder.error_message = result.get("StatusMssg", "RSR order failed")
            VendorOrder.raw_response = result
            VendorOrder.save()

            return Response(
                {"message": f"Failed to place RSR order", "data": result},
                status=status.HTTP_400_BAD_REQUEST
            )


class TrackOrderView(APIView):
    module_name = 'orders'
    permission_classes = [IsAuthenticated, IsOwnerOrHasPermission]

    def post(self, request, market_name, order_id):
        user = request.user
        if user and user.parent_id:
            user = user.parent

        # Try existing VendorOrderLog
        vendor_order = VendorOrderLog.objects.filter(
            order__orderId=order_id,
            order__market_name__iexact=market_name,
            enrollment__user=user,
        ).first()
        
        if not vendor_order:
            return Response(
                {"message": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if vendor_order.vendor.lower() == "rsr":
            rsr_client = RsrOrderApiClient(vendor_order)
            payload = rsr_client.build_check_order_payload(vendor_order)
            result = rsr_client.check_order(payload)
    
            if result.get("StatusCode") == "00":
                rsr_client.update_local_status(result)
                if vendor_order.status == VendorOrderLog.VendorOrderStatus.SHIPPED:
                    push_tracking_to_ebay(vendor_order)
                return Response(
                    {"message": "RSR order checked successfully", "data": result},
                    status=status.HTTP_200_OK
                )
            return Response(
                {"message": f"Failed to check RSR order", "data": result},
                status=status.HTTP_400_BAD_REQUEST
            )

        elif vendor_order.vendor.lower() == "fragrancex":
            fx_client = FrgxOrderApiClient(vendor_order)
            if fx_client.check_and_update_status():
                if vendor_order.status == VendorOrderLog.VendorOrderStatus.SHIPPED:
                    push_tracking_to_ebay(vendor_order)
                return Response(
                    {"message": "Tracking information updated successfully."},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"message": "Tracking information not updated."},
                    status=status.HTTP_400_BAD_REQUEST,
                )


class PushTrackingView(APIView):
    module_name = 'orders'
    permission_classes = [IsAuthenticated, IsOwnerOrHasPermission]

    def post(self, request, order_id):
        vendor_order = VendorOrderLog.objects.filter(order__orderId=order_id).first()
        if not vendor_order:
            return Response(
                {"message": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        res = push_tracking_to_ebay(vendor_order)
        if res["success"]:
            return Response(
                {"message": "Tracking pushed to eBay successfully", "data": res},
                status=status.HTTP_200_OK
            )
        
        return Response(
            {"message": "Failed to push tracking to eBay", "data": res},
            status=status.HTTP_400_BAD_REQUEST
        )


class GetFulfillmentView(APIView):
    module_name = 'orders'
    permission_classes = [IsAuthenticated, IsOwnerOrHasPermission]

    def post(self, request, order_id):
        user = request.user
        if user and user.parent_id:
            user = user.parent

        vendor_order = VendorOrderLog.objects.filter(order__orderId=order_id).first()
        if not vendor_order:
            return JsonResponse(
                {"message": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        market_name = vendor_order.order.market_name
        access_token = get_access_token(user.id, market_name)

        if not access_token:
            return JsonResponse(
                {"message": "Access token not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        url = vendor_order.fulfillment_url
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        response = requests.get(url, headers=headers)

        return JsonResponse(response.json(), status=response.status_code)
    
        

