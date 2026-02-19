from rest_framework.decorators import api_view, permission_classes
from ..utils import get_vendor_enrollment
import requests
from django.http import JsonResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from vendorActivities.apiSupplier import getFragranceXAuth
from accounts.models import User
from ..models import VendorOrderLog, OrdersOnEbayModel
from ..utils import get_ebay_order_details
from django.db.models import Q
import logging
import time
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware

logger = logging.getLogger(__name__)



class FrgxOrderApiClient:
    base_url = "https://apiordering.fragrancex.com/order"  
    
    def __init__(self, VendorOrder: VendorOrderLog):
        self.VendorOrder = VendorOrder
        # Get order details

        self.user = self.VendorOrder.enrollment.user
        self.market_name =  self.VendorOrder.order.market_name.capitalize()
        self.order_id = self.VendorOrder.order.orderId
        self.api_id = self.VendorOrder.enrollment.account.apiAccessId
        self.api_key = self.VendorOrder.enrollment.account.apiAccessKey
        
    def get_order_details(self):
        order_details = get_ebay_order_details(self.user.id, self.market_name, self.order_id)
        
        return order_details
    
    def build_bulk_payload(self, order_details):

        if not self.VendorOrder.reference_id:
            self.VendorOrder.reference_id = self.VendorOrder.order.orderId
            self.VendorOrder.save(
                update_fields=['reference_id']
            )
        
        # Build bulk order payload

        fulfillmentStartInstructions = order_details.get('fulfillmentStartInstructions', [{}])[0]
        shipTo = fulfillmentStartInstructions.get("shippingStep", {}).get("shipTo", {})
        fullname = shipTo.get("fullName", "Unknown").split(' ')
        firstName = fullname[0]
        lastName = fullname[1] if len(fullname) > 1 else ''
        contactAddress = shipTo.get("contactAddress", {})
        ShipAddress = contactAddress.get("addressLine1", "Unknown")
        city = contactAddress.get("city", "Unknown")
        state = contactAddress.get("stateOrProvince", "Unknown")
        zipcode = contactAddress.get("postalCode", "Unknown")
        country = contactAddress.get("countryCode", "Unknown")
        primaryPhone = shipTo.get("primaryPhone", {}).get("phoneNumber", "Unknown")
        
        items = []
        for item in order_details.get('lineItems', []):
            sku = item.get('sku', 'Unknown')
            quantity = item.get('quantity', 0)
            
            detail = {
                "ItemId": sku,
                "Quantity": quantity
            }
            items.append(detail)
        
        if not items:
            raise ValueError("No items found in order details to build the bulk order payload.")   
        
        # Define bulk order payload
        bulk_order = {
            "Orders": [
                {
                    "ShippingAddress": {
                        "FirstName": firstName,
                        "LastName": lastName,
                        "Address1": ShipAddress,
                        "Address2": "",
                        "City": city,
                        "State": state,
                        "ZipCode": zipcode,
                        "Country": country,
                        "Phone": primaryPhone,
                    },
                    "ShippingMethod": 0,
                    "ReferenceId": self.VendorOrder.reference_id,
                    "IsDropship": False,
                    "IsGiftWrapped": False,
                    "OrderItems": items
                }
            ],
            "BillingInfoSpecified": False
        }
        
        # save raw request
        self.VendorOrder.raw_request = bulk_order
        self.VendorOrder.save(update_fields=["raw_request"])
            
        return bulk_order
         
    def place_bulk_order(self, bulk_order):
        access_token = getFragranceXAuth(self.api_id, self.api_key)
        headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        }
        response = requests.post(f"{self.base_url}/PlaceBulkOrder", json=bulk_order, headers=headers, timeout=30)
        return response.json()
    
    def generate_reference(self, order_id):
        import uuid
        unique_suffix = str(uuid.uuid4())[:6]
        return f"SW-FX-{order_id}-{unique_suffix}"
    
    def check_order(self):
        access_token = getFragranceXAuth(self.api_id, self.api_key)

        url = f"https://apitracking.fragrancex.com/tracking/gettrackinginfo/{self.order_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        for attempt in range(3):
            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                return response.json()

            if response.status_code == 429:
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    f"FragranceX rate limit hit for order {self.order_id}, "
                    f"retrying in {wait}s (attempt {attempt + 1}/3)"
                )
                time.sleep(wait)
                continue

            logger.warning(
                f"FragranceX tracking API returned {response.status_code} for order {self.order_id}"
            )
            return {}

        # All retries exhausted on 429
        logger.error(f"FragranceX rate limit not resolved after 3 retries for order {self.order_id}")
        return None

    def update_local_status(self, data):
        vendor_order = self.VendorOrder
        tracking_number = vendor_order.tracking_number
        carrier = vendor_order.carrier
        shipped_date = vendor_order.shipped_at

        if not data:
            logger.info(
                f"FragranceX tracking API returned no data for order {self.order_id}"
            )
            return False

        elif not tracking_number or not carrier:
            tracking_number = data.get("TrackingNumber")
            carrier = data.get("Carrier")
            shipped_date_raw = data.get("DateShipped")
            tracking_url = data.get("TrackingLink")

            # Not shipped yet → stop here
            if not tracking_number or not carrier:
                logger.info(
                    f"Order {self.order_id} not shipped yet by FragranceX"
                )
                return False

            # Convert shipped date safely
            shipped_date = parse_datetime(shipped_date_raw) if shipped_date_raw else None
            if shipped_date and shipped_date.tzinfo is None:
                shipped_date = make_aware(shipped_date)
                
            # Update VendorOrderLog
            vendor_order.tracking_number = tracking_number
            vendor_order.carrier = carrier
            vendor_order.shipped_at = shipped_date
            vendor_order.tracking_url = tracking_url
            vendor_order.status = VendorOrderLog.VendorOrderStatus.SHIPPED
            vendor_order.save(
                update_fields=[
                    "tracking_number",
                    "carrier",
                    "shipped_at",
                    "tracking_url",
                    "status",
                ]
            )
            return True

        elif tracking_number and carrier:
            # Already had tracking info
            return True
        else:
            return False
            
    
        

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def place_order_fragrancex(request, market_name, orderid):
    # Get vendor enrollment details
    user = request.user
    if user and user.parent_id:
        user = user.parent
    
    
    VendorOrder = VendorOrderLog.objects.filter(
        order__orderId=orderid,
        order__market_name__iexact=market_name,
        enrollment__user=user,
        enrollment__vendor__name__iexact='Fragrancex'
    ).first()
    
    if not VendorOrder:
        order = OrdersOnEbayModel.objects.filter(
            orderId=orderid,
            market_name__iexact=market_name,
            user=user
        ).first()
        
        if not order:
            return JsonResponse(
                {"message": "Vendor order log not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        enrollment = get_vendor_enrollment(order.marketItemId)

        if not enrollment:
            return JsonResponse(
                {
                    "message": "Product is not linked to any active vendor enrollment.",
                    "order_id": orderid,
                    "market_item_id": order.marketItemId,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        VendorOrder = VendorOrderLog.objects.create(
            order=order,
            enrollment=enrollment,
            vendor='Fragrancex',
            status=VendorOrderLog.VendorOrderStatus.CREATED
        )
    elif VendorOrder.status in [
            VendorOrderLog.VendorOrderStatus.PROCESSING,
            VendorOrderLog.VendorOrderStatus.SHIPPED,
            VendorOrderLog.VendorOrderStatus.DELIVERED,
        ]:
        return JsonResponse(
            {"message": "Order is already placed with FragranceX."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
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
        return JsonResponse(
            {"message": "Order placed successfully.", "data": result, "order_info": bulk_order},
            status=status.HTTP_200_OK,
        )
    else:
        return JsonResponse(
            {"message": "Failed to place order.", "data": result, "order_info": bulk_order},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getTracking_fragranceX(request, orderId):
    try:        
        user = request.user
        if user and user.parent_id:
            user = user.parent
        
        # Lets get the enrollment from VendorOrderLog instead
        vendor_order = VendorOrderLog.objects.filter(
            Q(order__orderId=orderId) | Q(reference_id=orderId),
            enrollment__user=user,
            enrollment__vendor__name__iexact='Fragrancex'
        ).first()
        
        if not vendor_order:
            return JsonResponse(
                {"message": "Vendor order details not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if vendor_order.tracking_number and vendor_order.carrier:
            return JsonResponse(
                {"message": "Tracking already up to date."},
                status=status.HTTP_200_OK,
            )

        fx_client = FrgxOrderApiClient(vendor_order)
        data = fx_client.check_order()
        if data is None:
            return JsonResponse(
                {"message": "FragranceX rate limit reached. Please retry shortly."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        if fx_client.update_local_status(data):
            return JsonResponse(
                {"message": "Tracking information updated successfully.", "data": data},
                status=status.HTTP_200_OK,
            )
        else:
            return JsonResponse(
                {"message": "Tracking information not updated.", "data": data},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
    except Exception as e:
        # Handle other unexpected errors
        return JsonResponse(
            {"message": "An unexpected error occurred.", "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )