from django.db import models
from accounts.models import User
from vendorEnrollment.models import Generalproducttable
from cloudinary.models import CloudinaryField

# Create your models here. 
class MarketplaceEnronment(models.Model):
    _id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    marketplace_name = models.CharField(max_length=50, unique=False, null=True)
    region = models.CharField(max_length=50, null=True, unique=False)
    store_id = models.TextField(null=True, unique=False)
    store_logo = models.TextField(null=True, unique=False)
    fixed_percentage_markup = models.TextField(null=True, unique=False)
    fixed_markup = models.TextField(null=True, unique=False)
    enable_price_update = models.BooleanField(null=True, unique=False)
    enable_quantity_update = models.BooleanField(null=True, unique=False)
    maximum_quantity = models.TextField(null=True, unique=False)
    enable_charity = models.BooleanField(null=True, unique=False)
    charity_id = models.BigIntegerField(null=True, unique=False)
    donation_percentage = models.IntegerField(null=True, unique=False)
    enable_best_offer = models.BooleanField(null=True, unique=False)
    RIO_strategy = models.TextField(null=True, unique=False)
    min_profit_mergin = models.FloatField(null=True, unique=False)
    profit_margin = models.FloatField(null=True, unique=False)
    send_min_price = models.BooleanField(null=True, unique=False)
    warn_copyright_complaints = models.BooleanField(null=True, unique=False)
    warn_restriction_violation = models.BooleanField(null=True, unique=False)
    shipping_policy = models.TextField(null=True, unique=False)
    return_policy = models.TextField(null=True, unique=False)
    payment_policy = models.TextField(null=True, unique=False)
    refresh_token = models.TextField(null=False, unique=False)
    access_token = models.TextField(null=False, unique=False)
    

class AuthorizationCode(models.Model):
    authorization_code = models.TextField(null=False, unique=False)


class UploadedProductImage(models.Model):
    # image_url = CloudinaryField('image')
    image_url = models.ImageField(upload_to='productImage/', null=False, unique=False)
    image_name = models.CharField(max_length=100, null=False, unique=False)
    uploaded_date= models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, unique=False, null=False)
    product = models.ForeignKey(Generalproducttable, on_delete=models.CASCADE, unique=False, null=False)
