from rest_framework import serializers
from .models import CancelOrderModel, VendorOrderLog, OrdersOnEbayModel



class CancelOrderModelSerializer(serializers.ModelSerializer):
	class Meta:
		model = CancelOrderModel
		fields = [
			"cancel_reason",
		]
  

class VendorOrderLogSerializer(serializers.ModelSerializer):
    shipping_address = serializers.SerializerMethodField()
    price_summary = serializers.SerializerMethodField()

    def get_shipping_address(self, obj):
        vendor_name = obj.vendor.lower()
        if vendor_name == 'fragrancex':
            results = obj.raw_response.get("OrderResults", [])
            if not results:
                return None

            shipping_address = results[0].get("ShippingAddress", {})
            if not isinstance(shipping_address, dict):
                return None

            return {
                "name": f"{shipping_address.get('FirstName')} {shipping_address.get('LastName')}",
                "address1": shipping_address.get("Address1"),
                "address2": shipping_address.get("Address2"),
                "city": shipping_address.get("City"),
                "state": shipping_address.get("State"),
                "zip": shipping_address.get("Zipcode"),
                "county": shipping_address.get("County"),
                "country": shipping_address.get("Country"),
                "phone": shipping_address.get("Phone"),
            }

        elif vendor_name == 'rsr':
            address = obj.raw_response.get("Address", {})
            if not isinstance(address, dict):
                return None

            zip_code = address.get("Zip")
            plus4 = address.get("Plus4")
            full_zip = f"{zip_code}-{plus4}" if plus4 else zip_code

            return {
                "name": address.get("Name"),
                "address1": address.get("Address1"),
                "address2": address.get("Address2"),
                "city": address.get("City"),
                "state": address.get("State"),
                "zip": full_zip,
                "county": address.get("County"),
                "country": address.get("Country"),
                "phone": address.get("Phone"),
            }
        else:
            return None
    
    def get_price_summary(self, obj):
        vendor_name = obj.vendor.lower()
        if vendor_name == 'rsr':
            raw_response = obj.raw_response
            return {
                "subtotal": self._parse_money(raw_response.get("Subtotal")),
                "shipping": self._parse_money(raw_response.get("Shipping")),
                "cod": self._parse_money(raw_response.get("COD")),
                "total": self._parse_money(raw_response.get("Total")),
            }
        
        elif vendor_name == 'fragrancex':
            results = obj.raw_response.get("OrderResults", [])
            if not results:
                return None
            
            result = results[0]
            return {
                "subtotal": self._parse_money(result.get("SubTotal")),
                "shipping": self._parse_money(result.get("ShippingCharge")),
                "cod": self._parse_money(result.get("CodFee")),
                "total": self._parse_money(result.get("GrandTotal")),
            }

        else:
            return None


    def _parse_money(self, value):
        if not value:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return float(value.replace("$", "").replace(",", "").strip())
        return 0.0

            

    class Meta:
        model = VendorOrderLog
        fields = [
            "status",
            "reference_id",
            "carrier",
            "tracking_number",
            "tracking_url",
            "shipped_at",
            "delivered_at",
            "hold_reason",
            "error_message",
            "shipping_address",
            "price_summary"
        ]

class OrderSyncSerializer(serializers.ModelSerializer):
    vendor_orders = VendorOrderLogSerializer(many=True, read_only=True)

    class Meta:
        model = OrdersOnEbayModel
        fields = [
            '_id',
            'orderId',
            'creationDate',
            'buyer',
            'orderFulfillmentStatus',
            'vendor_name',
            'quantity',
            'lineItemCost',
			"sku",
			"title",
			"listingMarketplaceId",
			"purchaseMarketplaceId",
			"itemLocation",
			"image",
			"additionalImages",
			"description",
			"categoryId",
			"market_name",
			"localizeAspects",
            'vendor_orders'
        ]
