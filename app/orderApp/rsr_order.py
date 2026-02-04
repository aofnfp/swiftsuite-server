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
from datetime import datetime
from django.utils.timezone import make_aware
import re


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
    
    def validate_storename(self, storename: str) -> str:
        if not storename:
            return "Store Name"

        # Normalize
        parts = storename.strip().split()

        # Remove common business suffixes
        suffixes = {"llc", "ltd", "inc", "plc", "corp", "co"}
        parts = [p for p in parts if p.lower().strip(".") not in suffixes]

        if not parts:
            return "Store Name"

        # Ensure at least 2 tokens
        if len(parts) == 1:
            return f"{parts[0]} {parts[0]}"

        first, second = parts[0], parts[1]

        if len(first) < 2:
            first = second
        if len(second) < 2:
            second = first

        return f"{first} {second}"

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

    def parse_date(self, date_str):
        shipping_date = datetime.strptime(date_str, "%Y%m%d")
        if shipping_date:
            shipping_date = make_aware(shipping_date)
        return shipping_date

    def get_carrier(self, tracking_num: str) -> str:
        tracking_num = tracking_num.strip().replace(" ", "").upper()

        # UPS: 1Z + 16 alphanumeric (total 18)
        if re.fullmatch(r"1Z[A-Z0-9]{16}", tracking_num):
            return "UPS"

        # USPS: 
        # - 20–22 digits
        # - OR 13 alphanumeric ending with US
        if (
            re.fullmatch(r"\d{20,22}", tracking_num)
            or re.fullmatch(r"[A-Z0-9]{11}US", tracking_num)
        ):
            return "USPS"

        # FedEx: 12–15 digits
        if re.fullmatch(r"\d{12,15}", tracking_num):
            return "FedEx"

        return "Other"

    def update_local_status(self, result):
        if result.get("StatusCode") != "00":
            return False

        items = result.get("Items", [])
        is_shipped = True
        
        if not items:
            is_shipped = False

        tracking_num = ""
        date_shipped = ""

        for item in items:
            date_shipped = str(item.get("DateShipped", "")).strip(", ")
            tracking_num = str(item.get("TrackingNum", "")).strip(", ")
            
            # Check for "Pending" or empty values which indicate not shipped
            if "Pending" in date_shipped or "Pending" in tracking_num:
                is_shipped = False
                break
        
        if is_shipped:
            self.vendor_order_log.status = VendorOrderLog.VendorOrderStatus.SHIPPED
            self.vendor_order_log.tracking_number = tracking_num
            self.vendor_order_log.shipped_at = self.parse_date(date_shipped)
            self.vendor_order_log.carrier = self.get_carrier(tracking_num)
            self.vendor_order_log.save()
            return True
        else:
            self.vendor_order_log.status = VendorOrderLog.VendorOrderStatus.PROCESSING
            self.vendor_order_log.save()
            return False
    




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
        rsr_client.update_local_status(result)
        if vendor_order.status == VendorOrderLog.VendorOrderStatus.SHIPPED:
            push_tracking_to_ebay(vendor_order)
        
        return JsonResponse(
            {"message": "RSR order checked successfully", "data": result},
            status=status.HTTP_200_OK
        )
    
    return JsonResponse(
        {"message": f"Failed to check RSR order", "data": result},
        status=status.HTTP_400_BAD_REQUEST
    )
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def push_tracking_to_ebay(request, order_id):
    vendor_order = VendorOrderLog.objects.filter(order__orderId=order_id, status=VendorOrderLog.VendorOrderStatus.SHIPPED).first()
    if not vendor_order:
        return JsonResponse(
            {"message": "Order not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    from .utils import push_tracking_to_ebay
    if push_tracking_to_ebay(vendor_order):
        return JsonResponse(
            {"message": "Tracking pushed to eBay successfully"},
            status=status.HTTP_200_OK
        )
    
    return JsonResponse(
        {"message": "Failed to push tracking to eBay"},
        status=status.HTTP_400_BAD_REQUEST
    )