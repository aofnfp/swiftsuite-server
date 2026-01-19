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
                "WishQTY": item.get("quantity"),
            })

        payload = {
            "Username": self.username,
            "Password": self.password,
            "Storename": sellerId,
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
        
        
        return payload

    def place_order(self, payload):
        response = requests.post(
            f"{self.BASE_URL}/place-order",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=payload,
            timeout=30
        )
        return response.json()

    def check_order(self, payload):
        response = requests.post(
            f"{self.BASE_URL}/check-order",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=payload,
            timeout=30
        )
        return response.json()
    
    def generate_reference(self, order_id):
        import uuid
        unique_suffix = str(uuid.uuid4())[:6]
        return f"SW-RSR-{order_id}-{unique_suffix}"
    
    def validate_item(self, sku):
        response = requests.get(
            f"{self.BASE_URL}/get-items",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            params={
                "Username": self.username,
                "Password": self.password,
                "MfgPartNum": sku,
                "POS": self.pos
            },
            timeout=30
        )
        return response.json()



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
        
    # Initialize RSR client
    rsr_client = RsrOrderApiClient(vendor_order)
    order_details = rsr_client.get_order_details()
    payload = rsr_client.build_payload(order_details)
    result = rsr_client.place_order(payload)
    
    if result.get("StatusCode") == 0:
        vendor_order.status = VendorOrderLog.VendorOrderStatus.PROCESSING
        vendor_order.vendor_order_id = result.get("OrderNum") or vendor_order.reference_id
        vendor_order.raw_response = result
        vendor_order.save()

        return JsonResponse(
            {"message": "RSR order placed successfully", "data": result},
            status=status.HTTP_200_OK
        )

    vendor_order.status = VendorOrderLog.VendorOrderStatus.FAILED
    vendor_order.error_message = result.get("StatusMssg")
    vendor_order.raw_response = result
    vendor_order.save()

    return JsonResponse(
        {"message": f"Failed to place RSR order: {payload}", "data": result},
        status=status.HTTP_400_BAD_REQUEST
    )
