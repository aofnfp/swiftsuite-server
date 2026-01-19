from rest_framework.decorators import api_view, permission_classes
from .utils import get_vendor_enrollment
import requests
from django.http import JsonResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from vendorActivities.apiSupplier import getFragranceXAuth
from accounts.models import User
from .models import VendorOrderLog, OrdersOnEbayModel
from .utils import get_ebay_order_details
from django.db.models import Q
import logging
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
    
    
    def get_tracking_and_update_ebay(self):

        vendor_order = self.VendorOrder

        tracking_number = vendor_order.tracking_number
        carrier = vendor_order.carrier
        shipped_date = vendor_order.shipped_at

        # Fetch tracking only if missing
        if not tracking_number or not carrier:
            access_token = getFragranceXAuth(self.api_id, self.api_key)

            url = f"https://apitracking.fragrancex.com/tracking/gettrackinginfo/{self.order_id}"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code != 200:
                logger.warning(
                    f"FragranceX tracking API failed for order {self.order_id}"
                )
                return None

            data = response.json()

            tracking_number = data.get("TrackingNumber")
            carrier = data.get("Carrier")
            shipped_date_raw = data.get("DateShipped")
            tracking_url = data.get("TrackingLink")

            # Not shipped yet → stop here
            if not tracking_number or not carrier:
                logger.info(
                    f"Order {self.order_id} not shipped yet by FragranceX"
                )
                return None

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

            # Update local eBay order record
            OrdersOnEbayModel.objects.filter(
                id=vendor_order.order.id
            ).update(
                tracking_id=tracking_number,
                orderFulfillmentStatus="SHIPPED",
            )

        # Final validation before eBay call
        if not tracking_number or not carrier or not shipped_date:
            logger.warning(
                f"Skipping eBay tracking push for order {self.order_id}: incomplete tracking"
            )
            return None

        # Push to eBay
        from orderApp.views import OrderEbay 

        orderEbay = OrderEbay()
        return orderEbay.track_order_on_ebay(
            userid=vendor_order.enrollment.user.id,
            ebayorderid=self.order_id,
            tracking_number=tracking_number,
            carrier_code=carrier,
            line_item_id=vendor_order.order.lineItemId,
            shipped_date=shipped_date,
        )
            


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
        apiAccessId = vendor_order.enrollment.account.apiAccessId
        apiAccessKey = vendor_order.enrollment.account.apiAccessKey

        # Get FragranceX token
        token = getFragranceXAuth(apiAccessId, apiAccessKey)

        if not token:
            return JsonResponse(
                {"message": "Authentication with FragranceX failed."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # FragranceX API endpoint and headers
        url = f"https://apitracking.fragrancex.com/tracking/gettrackinginfo/{orderId}"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }

        # Make the GET request
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            return JsonResponse(data, status=status.HTTP_200_OK)
        
        elif response.status_code == 400:
            return JsonResponse(
                {
                    "message": "Tracking Information doesn't exists.",
                    "status_code": response.status_code,
                },
                status=response.status_code,
            )
        else:
            return JsonResponse(
            {
                "message": "Failed to fetch tracking information from FragranceX.",
                "status_code": response.status_code,
                "response": response.text,
            },
            status=response.status_code,
        )



    except requests.RequestException as e:
        # Handle network errors
        return JsonResponse(
            {"message": "An error occurred while communicating with the API.", "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        # Handle other unexpected errors
        return JsonResponse(
            {"message": "An unexpected error occurred.", "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )