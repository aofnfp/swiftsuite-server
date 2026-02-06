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
        # Ensure reference_id exists
        if not self.vendor_order_log.reference_id:
            self.vendor_order_log.reference_id = self.vendor_order_log.order.orderId
            self.vendor_order_log.save(update_fields=["reference_id"])

        # ---- Extract SHIP_TO info safely ----
        ship_to = {}

        for instruction in order_details.get("fulfillmentStartInstructions", []):
            if instruction.get("fulfillmentInstructionsType") == "SHIP_TO":
                ship_to = instruction.get("shippingStep", {}).get("shipTo", {})
                break

        contact_address = ship_to.get("contactAddress", {})
        phone = ship_to.get("primaryPhone", {})

        full_name = ship_to.get("fullName", "")
        email = ship_to.get("email", self.user.email)

        # ---- Build Items ----
        items = [
            {
                "PartNum": item.get("sku"),
                "WishQty": item.get("quantity"),
            }
            for item in order_details.get("lineItems", [])
        ]

        # ---- Payload ----
        payload = {
            "Username": self.username,
            "Password": self.password,
            "Storename": self.validate_storename(full_name),

            "ShipAddress": contact_address.get("addressLine1"),
            "ShipAddress2": contact_address.get("addressLine2"),
            "ShipCity": contact_address.get("city"),
            "ShipState": contact_address.get("stateOrProvince"),
            "ShipZip": contact_address.get("postalCode"),

            "ShipAccount": self.username,
            "ContactNum": phone.get("phoneNumber"),
            "PONum": self.vendor_order_log.reference_id,
            "Email": email,

            "Items": items,
            "POS": self.pos,
            "FillOrKill": 1,
        }

        # ---- Save raw request ----
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
        if not date_str:
            return None

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
        # RSR call itself failed
        if result.get("StatusCode") != "00":
            return False

        hold_status = (result.get("HoldStatus") or "").strip()

       
        if hold_status:
            self.vendor_order_log.status = VendorOrderLog.VendorOrderStatus.PROCESSING
            self.vendor_order_log.hold_reason = hold_status
            self.vendor_order_log.save(update_fields=["status", "hold_reason"])
            return False

        # If we get here, order is NOT on hold → clear previous hold
        if self.vendor_order_log.hold_reason:
            self.vendor_order_log.hold_reason = None

        items = result.get("Items", [])

        if not items:
            self.vendor_order_log.status = VendorOrderLog.VendorOrderStatus.PROCESSING
            self.vendor_order_log.save(update_fields=["status", "hold_reason"])
            return False

        for item in items:
            raw_date = str(item.get("DateShipped", "")).strip(", ")
            raw_tracking = str(item.get("TrackingNum", "")).strip(", ")

            # RSR uses empty or "Pending" for not shipped
            if (
                not raw_date
                or not raw_tracking
                or "PENDING" in raw_date.upper()
                or "PENDING" in raw_tracking.upper()
            ):
                self.vendor_order_log.status = VendorOrderLog.VendorOrderStatus.PROCESSING
                self.vendor_order_log.save(update_fields=["status", "hold_reason"])
                return False

            parsed_date = self.parse_date(raw_date)
            if not parsed_date:
                self.vendor_order_log.status = VendorOrderLog.VendorOrderStatus.PROCESSING
                self.vendor_order_log.save(update_fields=["status", "hold_reason"])
                return False

            self.vendor_order_log.status = VendorOrderLog.VendorOrderStatus.SHIPPED
            self.vendor_order_log.tracking_number = raw_tracking
            self.vendor_order_log.shipped_at = parsed_date
            self.vendor_order_log.carrier = self.get_carrier(raw_tracking)
            self.vendor_order_log.hold_reason = None

            self.vendor_order_log.save()
            return True

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
            from .utils import push_tracking_to_ebay
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
def push_tracking(request, order_id):
    vendor_order = VendorOrderLog.objects.filter(order__orderId=order_id).first()
    if not vendor_order:
        return JsonResponse(
            {"message": "Order not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    from .utils import push_tracking_to_ebay
    res = push_tracking_to_ebay(vendor_order)
    if res["success"]:
        return JsonResponse(
            {"message": "Tracking pushed to eBay successfully", "data": res},
            status=status.HTTP_200_OK
        )
    
    return JsonResponse(
        {"message": "Failed to push tracking to eBay", "data": res},
        status=status.HTTP_400_BAD_REQUEST
    )