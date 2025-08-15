from django.db import models
from vendorActivities.models import Vendors, Fragrancex, Lipsey, Cwr, Rsr, Zanders, Ssi
from accounts.models import User


# Create your models here.
class Account(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    vendor = models.ForeignKey(Vendors, on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=100, unique=True)
    ftp_username = models.CharField(max_length=50, null=True, unique=False)
    ftp_password = models.CharField(max_length=50, null=True, unique=False)
    host = models.CharField(max_length=255)
    apiAccessId = models.CharField(max_length=255, null=True)
    apiAccessKey = models.CharField(max_length=255, null=True)
    Username = models.CharField(max_length=255, null=True)
    Password = models.CharField(max_length=255, null=True)
    POS = models.CharField(max_length=255, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['name', 'user'], name='unique_account_per_user')
        ]



class Enrollment(models.Model):
    vendor = models.ForeignKey(Vendors, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    identifier = models.CharField(max_length=255, unique=True, blank=False, null=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='enrollments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Price options
    percentage_markup = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    fixed_markup = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_cost_average = models.BooleanField(default=False)
    stock_minimum = models.PositiveIntegerField(default=0, null=True)
    stock_maximum = models.PositiveIntegerField(default=0, null=True)
    update_inventory = models.BooleanField(default=False)
    send_orders = models.BooleanField(default=False)
    update_tracking = models.BooleanField(default=False)

    # Product Filters
    product_filter = models.JSONField(blank=True, null=True, default=list)
    product_category = models.JSONField(blank=True, null=True, default=list)
    brand = models.JSONField(blank=True, null=True, default=list)
    manufacturer = models.JSONField(blank=True, null=True, default=list)
    shippable = models.JSONField(blank=True, null=True, default=list)

    # Zander Field
    serialized = models.BooleanField(default=False)

    # CWR Fields
    truck_freight = models.BooleanField(default=False) 
    oversized = models.BooleanField(default=False)
    third_party_marketplaces = models.BooleanField(default=False)
    returnable = models.BooleanField(default=False)
    
    def __str__(self):
        return self.identifier

class BackgroundTask(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    result = models.TextField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

class FragrancexUpdate(models.Model):
    vendor = models.ForeignKey(Vendors, on_delete=models.CASCADE)
    product = models.ForeignKey(Fragrancex, on_delete=models.CASCADE)
    sku = models.CharField(max_length=255, blank=True, null=True)
    upc = models.CharField(max_length=255, blank=True, null=True)
    mpn = models.CharField(max_length=255, blank=True, null=True)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
class SsiUpdate(models.Model):
    vendor = models.ForeignKey(Vendors, on_delete=models.CASCADE)
    product = models.ForeignKey(Ssi, on_delete=models.CASCADE)
    sku = models.CharField(max_length=255, blank=True, null=True)
    upc = models.CharField(max_length=255, blank=True, null=True)
    mpn = models.CharField(max_length=255, blank=True, null=True)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
class LipseyUpdate(models.Model):
    vendor = models.ForeignKey(Vendors, on_delete=models.CASCADE)
    product = models.ForeignKey(Lipsey, on_delete=models.CASCADE)
    sku = models.CharField(max_length=255, blank=True, null=True)
    upc = models.CharField(max_length=255, blank=True, null=True)
    mpn = models.CharField(max_length=255, blank=True, null=True)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
     
class CwrUpdate(models.Model):
    vendor = models.ForeignKey(Vendors, on_delete=models.CASCADE)
    product = models.ForeignKey(Cwr, on_delete=models.CASCADE)
    sku = models.CharField(max_length=255, blank=True, null=True)
    upc = models.CharField(max_length=255, blank=True, null=True)
    mpn = models.CharField(max_length=255, blank=True, null=True)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity = models.PositiveIntegerField(default=1)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
class RsrUpdate(models.Model):
    vendor = models.ForeignKey(Vendors, on_delete=models.CASCADE)
    product = models.ForeignKey(Rsr, on_delete=models.CASCADE)
    sku = models.CharField(max_length=255, blank=True, null=True)
    upc = models.CharField(max_length=255, blank=True, null=True)
    mpn = models.CharField(max_length=255, blank=True, null=True)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity = models.PositiveIntegerField(default=1)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
class ZandersUpdate(models.Model):
    vendor = models.ForeignKey(Vendors, on_delete=models.CASCADE)
    product = models.ForeignKey(Zanders, on_delete=models.CASCADE)
    sku = models.CharField(max_length=255, blank=True, null=True)
    upc = models.CharField(max_length=255, blank=True, null=True)
    mpn = models.CharField(max_length=255, blank=True, null=True)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Generalproducttable(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vendorenrollment_generalproducts')
    product_id = models.TextField(null=True)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, null=True)
    vendor_name = models.CharField(max_length=255, null=True)
    sku = models.CharField(db_column='SKU', max_length=255, blank=True, null=True) 
    quantity = models.TextField(db_column='Quantity', blank=True, null=True)  
    upc = models.CharField(db_column='UPC', max_length=255, blank=True, null=True)  
    title = models.CharField(db_column='Title', max_length=255, blank=True, null=True)  
    detailed_description = models.TextField(db_column='Detailed_Description', blank=True, null=True)  
    image = models.CharField(db_column='Image', max_length=255, blank=True, null=True)  
    category = models.CharField(db_column='Category', max_length=255, blank=True, null=True)  
    category_id = models.IntegerField(db_column='Category_ID', blank=True, null=True)  
    msrp = models.TextField(db_column='MSRP', blank=True, null=True)  
    mpn = models.CharField(db_column='MPN', max_length=255, blank=True, null=True)  
    map = models.TextField(db_column='MAP', blank=True, null=True)  
    dimensionh = models.DecimalField(db_column='DimensionH', max_digits=10, decimal_places=6, blank=True, null=True)  
    dimensionl = models.DecimalField(db_column='DimensionL', max_digits=10, decimal_places=6, blank=True, null=True)  
    dimensionw = models.DecimalField(db_column='DimensionW', max_digits=10, decimal_places=6, blank=True, null=True)  
    shipping_weight = models.DecimalField(db_column='Shipping_Weight', max_digits=10, decimal_places=6, blank=True, null=True)  
    shipping_length = models.DecimalField(db_column='Shipping_Length', max_digits=10, decimal_places=6, blank=True, null=True)  
    shipping_width = models.DecimalField(db_column='Shipping_Width', max_digits=10, decimal_places=6, blank=True, null=True)  
    shipping_height = models.TextField(db_column='Shipping_Height', blank=True, null=True)  
    model = models.CharField(db_column='Model', max_length=255, blank=True, null=True)  
    price = models.DecimalField(db_column='Price', max_digits=10, decimal_places=2, blank=True, null=True)  
    brand = models.CharField(db_column='Brand', max_length=255, blank=True, null=True)  
    manufacturer = models.CharField(db_column='Manufacturer', max_length=255, blank=True, null=True)  
    prop_65 = models.IntegerField(db_column='Prop_65', blank=True, null=True)  
    prop_65_description = models.TextField(db_column='Prop_65_Description', blank=True, null=True)  
    manufacturer_id = models.IntegerField(db_column='Manufacturer_Id', blank=True, null=True)  
    date_created = models.DateField(db_column='Date_Created', blank=True, null=True)  
    thumbnail = models.CharField(db_column='Thumbnail', max_length=255, blank=True, null=True)    
    features = models.TextField(db_column='Features', blank=True, null=True)  
    active = models.BooleanField(default=False)
    total_product_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)