from rest_framework import serializers
from .models import CancelOrderModel, VendorOrderLog, OrdersOnEbayModel



class CancelOrderModelSerializer(serializers.ModelSerializer):
	class Meta:
		model = CancelOrderModel
		fields = [
			"cancel_reason",
		]
  

class VendorOrderLogSerializer(serializers.ModelSerializer):
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
        ]

class OrderSyncSerializer(serializers.ModelSerializer):
    vendor_orders = VendorOrderLogSerializer(many=True, read_only=True)

    class Meta:
        model = OrdersOnEbayModel
        fields = [
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
