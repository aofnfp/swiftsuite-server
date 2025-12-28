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


class FrgxOrderApiClient:
    def __init__(self):
        self.api_id = None
        self.api_key = None
        self.base_url = "https://apiordering.fragrancex.com/order"  
        
    def get_order_details(self, VendorOrder: VendorOrderLog):
        # Get order details
        self.user = VendorOrder.enrollment.user
        self.market_name =  VendorOrder.order.market_name.capitalize()
        self.order_id = VendorOrder.order.orderId
        self.api_id = VendorOrder.enrollment.account.apiAccessId
        self.api_key = VendorOrder.enrollment.account.apiAccessKey

        order_details = get_ebay_order_details(self.user.id, self.market_name, self.order_id)
        
        return order_details
    
    def build_bulk_payload(self, order_details):
        # Build bulk order payload

        fulfillmentStartInstructions = order_details.get('fulfillmentStartInstructions', [])[0]
        shipTo = fulfillmentStartInstructions.get("shippingStep", {}).get("shipTo", {})
        fullname = shipTo.get("fullName", "Unknown").split(' ')
        firstName = fullname[0]
        lastName = fullname[1]
        contactAddress = shipTo.get("contactAddress", {})
        ShipAddress = contactAddress.get("addressLine1", "Unknown")
        city = contactAddress.get("city", "Unknown")
        state = contactAddress.get("stateOrProvince", "Unknown")
        zipcode = contactAddress.get("postalCode", "Unknown")
        country = contactAddress.get("countryCode", "Unknown")
        primaryPhone = shipTo.get("primaryPhone", {}).get("phoneNumber", "Unknown")
        
        items = []
        for item in order_details.get('lineItems'):
            sku = item.get('sku', 'Unknown'),
            quantity = item.get('quantity', 0),
            
            detail = {
                "ItemId": sku[0], 
                "Quantity": quantity[0]
            }
            items.append(detail)
            
        
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
                    "ReferenceId": self.generate_reference(self.order_id),
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
        response = requests.post(f"{self.base_url}/PlaceBulkOrder", json=bulk_order, headers=headers)
        return response.json()
    
    def generate_reference(self, order_id):
        import uuid
        unique_suffix = str(uuid.uuid4())[:4]
        return f"SW-FX-{order_id}-{unique_suffix}"
    
    


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def place_order_fragrancex(request, userid, market_name, ebayorderid):
    # Get vendor enrollment details
    user = User.objects.filter(id=userid).first()
    if user and user.parent_id:
        userid = user.parent_id
        user = User.objects.filter(id=userid).first()
    
    
    VendorOrder = VendorOrderLog.objects.filter(
        order__orderId=ebayorderid,
        order__market_name__iexact=market_name,
        enrollment__user=user,
        enrollment__vendor__name__iexact='Fragrancex'
    ).first()
    
    if not VendorOrder:
        OrdersOnEbayModel_obj = OrdersOnEbayModel.objects.filter(
            orderId=ebayorderid,
            market_name__iexact=market_name,
            user=user
        ).first()
        
        if not OrdersOnEbayModel_obj:
            return JsonResponse(
                {"message": "Vendor order log not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        VendorOrder = VendorOrderLog.objects.create(
            order=OrdersOnEbayModel_obj,
            enrollment=get_vendor_enrollment(OrdersOnEbayModel_obj.marketItemId),
            vendor='Fragrancex',
            status=VendorOrderLog.VendorOrderStatus.CREATED
        )
    
    # Initialize client
    order_client = FrgxOrderApiClient()
    
    ordered_details = order_client.get_order_details(VendorOrder)
    
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
        # Get vendor enrollment details
        from vendorEnrollment.models import Enrollment
        
        user = request.user
        if user and user.parent_id:
            user = user.parent
            
        enrolment_details = Enrollment.objects.filter(
            user=user, vendor__name__iexact='Fragrancex'
        ).first()

        if not enrolment_details:
            return JsonResponse(
                {"message": "Vendor enrollment details not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        apiAccessId = enrolment_details.vendor.api_access_id
        apiAccessKey = enrolment_details.vendor.api_access_key

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