from rest_framework.decorators import api_view, permission_classes
from vendorApp.models import VendoEnronment
import requests
from django.http import JsonResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .serializer import PlaceOrderSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getOrderInfo(request, userid, market_name, ebayorderid):
    try:
        # Get enrolment details
        enrolment_details = VendoEnronment.objects.filter(
            user_id=request.user.id, vendor_name='RSR'
        ).first()
        
        if not enrolment_details:
            return JsonResponse(
                {"error": "Vendor enrolment details not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        username = enrolment_details.Username
        password = enrolment_details.Password
        POS = enrolment_details.POS
        
        # Get order details
        ebay_orderDetails_url = f"https://service.swiftsuite.app/orderApp/get_ordered_item_details/{userid}/{market_name}/{ebayorderid}/"
        response = requests.get(ebay_orderDetails_url)
        
        if response.status_code != 200:
            return JsonResponse(
                {"error": "Failed to fetch order details."},
                status=response.status_code,
            )

        Details = response.json()
        
        # Extract required details
        ordered_details = Details.get('ordered_details', {})
        POnum = ordered_details.get('orderId', 'Unknown') 
        buyerInfo = ordered_details.get('buyer').get('buyerRegistrationAddress', {})
        contactAddress = buyerInfo.get('contactAddress', 'Unknown')
        ShipAddress = contactAddress.get('addressLine1', 'Unknown')
        ShipCity = contactAddress.get('city', 'Unknown')
        ShipState = contactAddress.get('stateOrProvince', 'Unknown')
        ShipZip = contactAddress.get('postalCode', 'Unknown')
        ShipAcccount = username
        ContactNum = buyerInfo.get('primaryPhone', {}).get('phoneNumber', 'Unknown')
        Email = request.user.email
        
        
        items = []
        for item in ordered_details.get('lineItems'):
            sku = item.get('sku', 'Unknown'),
            quantity = item.get('quantity', 0),
            
            detail = {
                "PartNum": sku[0], 
                "WishQTY": quantity[0]
            }
            items.append(detail)

        print(items)
        
        # Create payload
        payload = {
            "Username": username,
            "Password": password,
            "ShipAddress": ShipAddress,
            "ShipCity": ShipCity,
            "ShipState": ShipState,
            "ShipZip": ShipZip,
            "ShipAcccount": ShipAcccount,
            "ContactNum": ContactNum,
            "PONum": POnum,
            "Email": Email,
            "Items": items,
            "POS": POS,
            "FillOrKill": 1,
        }

        return JsonResponse(payload, status=status.HTTP_200_OK)

    except Exception as e:
        return JsonResponse(
            {"error": f"An unexpected error occurred: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    
@api_view(['POST'])
def place_order(request):
    serializer = PlaceOrderSerializer(data=request.data)
    if serializer.is_valid():
        try:
            # Extract validated data
            payload = serializer.validated_data
            

            # API endpoint and headers
            url = "https://www.rsrgroup.com/api/rsrbridge/1.0/pos/place-order"
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}

            # Make POST request
            response = requests.post(url, headers=headers, json=payload)

            # Check response status
            if response.status_code == 200:
                data = response.json()
                if data["StatusCode"] != 00:
                    return JsonResponse({"error": f"Failed to place order: {data['StatusMssg']}"}, status=status.HTTP_400_BAD_REQUEST)
                
                return JsonResponse(
                        {"message": "Order placed successfully!", "data": data},
                        status=status.HTTP_201_CREATED,
                    )
            else:
                return JsonResponse(
                    {
                        "message": "Failed to place order",
                        "error": response.json(),
                        "status_code": response.status_code,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except requests.RequestException as e:
            # Handle network or request errors
            return JsonResponse(
                {"message": "An error occurred while making the request.", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            # Handle unexpected errors
            return JsonResponse(
                {"message": "An unexpected error occurred.", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # If serializer is invalid, return validation errors
    return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def checkOrder(request):
    serializer = PlaceOrderSerializer(data=request.data)
    
    if serializer.is_valid():
        try:
            # Extract validated data
            payload = serializer.validated_data

            # API endpoint and headers
            url = "https://www.rsrgroup.com/api/rsrbridge/1.0/pos/check-order"
            headers = {'Content-Type': 'application/x-www-form-urlencoded'} 
            
            # Make the API request
            response = requests.post(url, headers=headers, json=payload)

            # Check the response status
            if response.status_code == 200:
                data = response.json()
                return JsonResponse(
                    {"message": "Order status retrieved successfully!", "data": data},
                    status=status.HTTP_200_OK
                )
            else:
                return JsonResponse(
                    {
                        "message": "Failed to retrieve order status",
                        "error": response.json(),
                        "status_code": response.status_code
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        except requests.RequestException as e:
            # Handle request exceptions (e.g., network errors)
            return JsonResponse(
                {"message": "An error occurred while communicating with the API.", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            # Handle unexpected errors
            return JsonResponse(
                {"message": "An unexpected error occurred.", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # If serializer is invalid, return validation errors
    return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    
    