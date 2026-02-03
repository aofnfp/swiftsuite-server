import requests
from .utils import get_ebay_order_details
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import VendorOrderLog
from django.shortcuts import get_object_or_404
from vendorEnrollment.models import Enrollment
from accounts.models import User
from .models import OrdersOnEbayModel
from .utils import get_vendor_enrollment
import logging
from django.db import transaction


logger = logging.getLogger(__name__)


class RsrOrderApiClient:
    BASE_URL = "https://www.rsrgroup.com/api/rsrbridge/1.0/pos"

    def __init__(self, vendor_order_log):
        self.vendor_order_log = vendor_order_log
        self.enrollment = vendor_order_log.enrollment
        self.user = self.enrollment.user

        self.username = self.enrollment.account.Username
        self.password = self.enrollment.account.Password
        self.pos = self.enrollment.account.POS

    def get_order_details(self):
        order = self.vendor_order_log.order
        return get_ebay_order_details(
            self.user.id,
            order.market_name.capitalize(),
            order.orderId
        )
    
    def validate_storename(self, storename):
        first, last = storename.split(" ")
        if len(first) < 2:
            first = last
        elif len(last) < 2:
            last = first
        return f"{first} {last}"

    def build_payload(self, order_details):
        if not self.vendor_order_log.reference_id:
            self.vendor_order_log.reference_id = self.vendor_order_log.order.orderId
            self.vendor_order_log.save(update_fields=["reference_id"])

        buyer = order_details.get("buyer", {}).get("buyerRegistrationAddress", {})
        address = buyer.get("contactAddress", {})
        sellerId = buyer.get("fullName")

        items = []
        for item in order_details.get("lineItems", []):
            items.append({
                "PartNum": item.get("sku"),
                "WishQty": item.get("quantity"),
            })

        payload = {
            "Username": self.username,
            "Password": self.password,
            "Storename": self.validate_storename(sellerId),
            "ShipAddress": address.get("addressLine1"),
            "ShipCity": address.get("city"),
            "ShipState": address.get("stateOrProvince"),
            "ShipZip": address.get("postalCode"),
            "ShipAccount": self.username,
            "ContactNum": buyer.get("primaryPhone", {}).get("phoneNumber"),
            "PONum": self.vendor_order_log.reference_id,
            "Email": self.user.email,
            "Items": items,
            "POS": self.pos,
            "FillOrKill": 1,
        }
        
        # save raw request
        self.vendor_order_log.raw_request = payload
        self.vendor_order_log.save(update_fields=["raw_request"])
        
        return payload

    def place_order(self, payload):
        response = requests.post(
            f"{self.BASE_URL}/place-order",
            json=payload, 
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        return response.json()

    def build_check_order_payload(self, order_log):
        payload = {
            "Username": self.username,
            "Password": self.password,
            "POS": self.pos,
        }

        if order_log.vendor_order_id:
            payload["WebRef"] = order_log.vendor_order_id 

        if order_log.reference_id:
            payload["PONum"] = order_log.reference_id 

        if order_log.raw_request:
            payload["Items"] = order_log.raw_request.get("Items")
            

        return payload

    def check_order(self, payload):
        response = requests.post(
            f"{self.BASE_URL}/check-order",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30
        )
        return response.json()
    
    def generate_reference(self, order_id):
        import uuid
        unique_suffix = str(uuid.uuid4())[:6]
        return f"SW-RSR-{order_id}-{unique_suffix}"


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def place_order_rsr(request, market_name, orderid):
    # Resolve parent account
    user = request.user
    if user and user.parent_id:
        user = user.parent

    # Try existing VendorOrderLog
    vendor_order = VendorOrderLog.objects.filter(
        order__orderId=orderid,
        order__market_name__iexact=market_name,
        enrollment__user=user,
        enrollment__vendor__name__iexact='RSR'
    ).first()
    
    if not vendor_order:
        order = OrdersOnEbayModel.objects.filter(
            orderId=orderid,
            market_name__iexact=market_name,
            user=user
        ).first()

        if not order:
            return JsonResponse(
                {"message": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        
        enrollment = get_vendor_enrollment(order.marketItemId)
        if not enrollment:
            return JsonResponse(
                {"message": "Vendor enrollment for RSR not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        vendor_order = VendorOrderLog.objects.create(
            order=order,
            enrollment=enrollment,
            vendor='RSR',
            status=VendorOrderLog.VendorOrderStatus.CREATED
        )
        
    elif vendor_order.status in [
            VendorOrderLog.VendorOrderStatus.PROCESSING, 
            VendorOrderLog.VendorOrderStatus.DELIVERED,
            VendorOrderLog.VendorOrderStatus.SHIPPED
        ]:
        return JsonResponse(
            {"message": "Order has already been placed with RSR."},
            status=status.HTTP_400_BAD_REQUEST
        )
        
    # Initialize RSR client
    rsr_client = RsrOrderApiClient(vendor_order)
    order_details = rsr_client.get_order_details()
    payload = rsr_client.build_payload(order_details)
    result = rsr_client.place_order(payload)
    
    
    if result.get("StatusCode") == "00":
        vendor_order.status = VendorOrderLog.VendorOrderStatus.PROCESSING
        vendor_order.vendor_order_id = (
            result.get("ConfirmResp") or result.get("WebRef")
        )
        vendor_order.raw_response = result
        vendor_order.save()
        
        return JsonResponse(
            {"message": "RSR order placed successfully", "data": result},
            status=status.HTTP_200_OK
        )

    vendor_order.status = VendorOrderLog.VendorOrderStatus.FAILED
    vendor_order.error_message = result.get("StatusMssg", "RSR order failed")
    vendor_order.raw_response = result
    vendor_order.save()

    return JsonResponse(
        {"message": f"Failed to place RSR order", "data": result},
        status=status.HTTP_400_BAD_REQUEST
    )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_order_rsr(request, market_name, orderid):
    # Resolve parent account
    user = request.user
    if user and user.parent_id:
        user = user.parent

    # Try existing VendorOrderLog
    vendor_order = VendorOrderLog.objects.filter(
        order__orderId=orderid,
        order__market_name__iexact=market_name,
        enrollment__user=user,
        enrollment__vendor__name__iexact='RSR'
    ).first()
    
    if not vendor_order:
        return JsonResponse(
            {"message": "Order not found"},
            status=status.HTTP_404_NOT_FOUND
        )
        
    rsr_client = RsrOrderApiClient(vendor_order)
    payload = rsr_client.build_check_order_payload(vendor_order)
    result = rsr_client.check_order(payload)
    
    if result.get("StatusCode") == "00":
        items = result.get("Items", [])
        is_shipped = True
        
        if not items:
            is_shipped = False

        for item in items:
            date_shipped = str(item.get("DateShipped", ""))
            tracking_num = str(item.get("TrackingNum", ""))
            
            # Check for "Pending" or empty values which indicate not shipped
            if "Pending" in date_shipped or "Pending" in tracking_num:
                is_shipped = False
                break
        
        if is_shipped:
            vendor_order.status = VendorOrderLog.VendorOrderStatus.SHIPPED
        else:
            vendor_order.status = VendorOrderLog.VendorOrderStatus.PROCESSING
            
        vendor_order.save()
        
        return JsonResponse(
            {"message": "RSR order checked successfully", "data": result},
            status=status.HTTP_200_OK
        )
    
    return JsonResponse(
        {"message": f"Failed to check RSR order", "data": result},
        status=status.HTTP_400_BAD_REQUEST
    )
    