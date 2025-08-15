from rest_framework.decorators import api_view, permission_classes
from vendorApp.models import VendoEnronment
import requests
from django.http import JsonResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from vendorApp.apiSupplier import getFragranceXAuth



class FrgxOrderApiClient:
    def __init__(self, api_id, api_key):
        self.api_id = api_id
        self.api_key = api_key
        self.base_url = "https://apiordering.fragrancex.com/order"  
    
    def place_bulk_order(self, order_data):
        headers = {
            "Content-Type": "application/json",
            "API-ID": self.api_id,
            "API-KEY": self.api_key
        }
        response = requests.post(f"{self.base_url}/PlaceBulkOrder", json=order_data, headers=headers)
        return response.json()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def place_order_fragrancex(request, userid, market_name, ebayorderid):
    # Get vendor enrollment details
    enrolment_details = VendoEnronment.objects.filter(
        user_id=request.user.id, vendor_name='FragranceX'
    ).first()

    if not enrolment_details:
        return JsonResponse(
            {"message": "Vendor enrollment details not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    apiAccessId = enrolment_details.apiAccessId
    apiAccessKey = enrolment_details.apiAccessKey
    
 
    # Get order details
    ebay_orderDetails_url = f"https://service.swiftsuite.app/orderApp/get_ordered_item_details/{userid}/{market_name}/{ebayorderid}/"
    response = requests.get(ebay_orderDetails_url)
    
    if response.status_code != 200:
        return JsonResponse(
            {"error": "Failed to fetch order details."},
            status=response.status_code,
        )

    Details = response.json()
    ordered_details = Details.get('ordered_details', {})
    fulfillmentStartInstructions = ordered_details.get('fulfillmentStartInstructions', [])[0]
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
    for item in ordered_details.get('lineItems'):
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
                "ReferenceId": ebayorderid,
                "IsDropship": False,
                "IsGiftWrapped": False,
                "OrderItems": items
            }
        ],
        "BillingInfoSpecified": False
    }
    
    
    # Initialize client
    order_client = FrgxOrderApiClient(apiAccessId , apiAccessKey)
    
    # Place the order
    result = order_client.place_bulk_order(bulk_order)
   
    if result.get("Success", False):
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
        enrolment_details = VendoEnronment.objects.filter(
            user_id=request.user.id, vendor_name='FragranceX'
        ).first()

        if not enrolment_details:
            return JsonResponse(
                {"message": "Vendor enrollment details not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        apiAccessId = enrolment_details.apiAccessId
        apiAccessKey = enrolment_details.apiAccessKey

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