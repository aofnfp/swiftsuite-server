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
    ebayItemId = models.CharField(null=True, unique=False, max_length=155)
    itemEbayStatus = models.CharField(null=True, unique=False, max_length=155)
    legacyItemId = models.TextField(null=True, unique=False)
    localizeAspects = models.CharField(null=True, unique=False, max_length=155)