from django.db import models
from accounts.models import User

# Create your models here.
class CancelOrderModel(models.Model):
    cancel_reason = models.CharField(null=False, unique=True, max_length=155)
    
class OrdersOnEbayModel(models.Model):
    _id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    orderId = models.CharField(null=False, unique=True, max_length=155)
    legacyOrderId = models.CharField(null=False, unique=True, max_length=155)
    creationDate = models.DateTimeField(unique=False, null=True, )
    orderFulfillmentStatus = models.CharField(null=False, unique=False, max_length=155)
    orderPaymentStatus = models.CharField(null=False, unique=False, max_length=155)
    sellerId = models.CharField(null=False, unique=False, max_length=155)
    buyer = models.TextField(null=True, unique=False)
    cancelStatus = models.TextField(null=True, unique=False)
    pricingSummary = models.TextField(null=True, unique=False)
    paymentSummary = models.TextField(null=True, unique=False)
    fulfillmentStartInstructions = models.TextField(null=True, unique=False)
    sku = models.CharField(null=False, unique=False, max_length=155)
    title = models.CharField(null=False, unique=False, max_length=155)
    lineItemCost = models.CharField(null=False, unique=False, max_length=155)
    quantity = models.CharField(null=False, unique=False, max_length=155)
    listingMarketplaceId = models.CharField(null=False, unique=False, max_length=155)
    purchaseMarketplaceId = models.CharField(null=False, unique=False, max_length=155)
    itemLocation = models.TextField(null=True, unique=False)
    image = models.TextField(null=True, unique=False)
    additionalImages = models.TextField(null=True, unique=False)
    mpn = models.CharField(null=True, unique=False, max_length=155)
    description = models.TextField(null=True, unique=False)
    categoryId = models.CharField(null=True, unique=False, max_length=155)
    vendor_name = models.CharField(null=True, unique=False, max_length=155)
    tracking_id = models.CharField(null=True, unique=False, max_length=155)
    marketItemId = models.CharField(null=True, unique=False, max_length=155)
    itemMarketStatus = models.CharField(null=True, unique=False, max_length=155)
    market_name = models.CharField(null=True, unique=False, max_length=155)
    legacyItemId = models.TextField(null=True, unique=False)
    localizeAspects = models.TextField(null=True, unique=False)
    last_updated = models.DateTimeField(auto_now=True)
    
    

class VendorOrderLog(models.Model):
    
    class VendorOrderStatus(models.TextChoices):
        CREATED = "created", "Created"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
    
    
    
    order = models.ForeignKey(
        "orderApp.OrdersOnEbayModel",
        on_delete=models.CASCADE,
        related_name="vendor_orders"
    )

    enrollment = models.ForeignKey(
        "vendorEnrollment.Enrollment",
        on_delete=models.PROTECT,
        related_name="vendor_orders"
    )

    vendor = models.CharField(
        max_length=50,
        db_index=True
    )

    vendor_order_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True
    )

    status = models.CharField(
        max_length=30,
        choices=VendorOrderStatus.choices,
        default=VendorOrderStatus.CREATED
    )
    
    reference_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True
    )

    # Shipping
    carrier = models.CharField(max_length=50, null=True, blank=True)
    tracking_number = models.CharField(max_length=100, null=True, blank=True)
    tracking_url = models.URLField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Vendor response / payload
    raw_request = models.JSONField(null=True, blank=True)
    raw_response = models.JSONField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f"{self.vendor} | {self.order_id} | {self.status}"
