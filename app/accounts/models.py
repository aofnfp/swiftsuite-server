from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from .manager import UserManager
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone

# Create your models here.
class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(max_length = 255, unique = True, verbose_name = _("Email Address"))
    first_name = models.CharField(max_length = 100, verbose_name = _('First Name'))
    last_name = models.CharField(max_length = 100, verbose_name = _('Last Name'))
    profile_image = models.ImageField(upload_to='ProfileImages/', null=True, blank=True)
    is_staff = models.BooleanField(default = False)
    is_superuser = models.BooleanField(default = False )
    is_verified = models.BooleanField(default = False )
    is_active = models.BooleanField(default = True )
    date_joined = models.DateTimeField(auto_now_add = True)
    last_login = models.DateTimeField(auto_now = True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='subaccounts')
    tier = models.ForeignKey('Tier', null=True, blank=True, on_delete=models.SET_NULL)
    phone = models.CharField(max_length=15, null=True, blank=True)

    USERNAME_FIELD = "email"

    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    def __str__(self):
        return self.email
    
    @property
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def tokens(self):
        refresh = RefreshToken.for_user(self)
        return {
            'refresh':str(refresh),
            'access':str(refresh.access_token)
        }
    
    @property
    def is_subaccount(self):
        return self.parent is not None
    
    @property
    def can_add_subaccount(self):
        return self.tier and self.subaccounts.count() < self.tier.max_subaccounts
    
    @property
    def subscribed(self):
        if hasattr(self, 'tier_subscription'):
            return self.tier_subscription.is_active()
        return False

class OneTimePassword(models.Model):

   user = models.OneToOneField(User, on_delete = models.CASCADE)
   code = models.CharField(max_length = 6, unique = True)

   def __str__(self):
       return f"{self.user.first_name}--passcode"
       
class Module(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name           
    
class SubAccountPermissions(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='permissions')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, null=True)
    can_view = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('user', 'module')
        

    def __str__(self):
        return f"{self.user.email} - {self.module.name} permissions"
    
    
class Tier(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)

    # Limits
    included_orders = models.PositiveIntegerField(default=0)
    extra_order_cost = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    
    included_stores = models.PositiveIntegerField(default=0)
    extra_store_cost = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    store_sku_limit = models.PositiveIntegerField(default=250000)
    extra_sku_cost = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)  # per 10k SKUs

    included_vendors = models.PositiveIntegerField(default=0)
    extra_vendor_cost = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    
    max_subaccounts = models.PositiveIntegerField(default=0)

    # Feature flags
    inventory_sync = models.BooleanField(default=False)
    api_access = models.BooleanField(default=False)
    branded_tracking = models.BooleanField(default=False)
    dedicated_success_manager = models.BooleanField(default=False)
    white_label_branding = models.BooleanField(default=False)
    advanced_analytics = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name


class Subscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tier_subscription')
    tier = models.ForeignKey(Tier, on_delete=models.CASCADE, related_name="subscriptions")
    subscribed_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.email} subscribed to {self.tier.name}"
    
    def is_active(self):
        return timezone.now() < self.expires_at
    
    
class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tier = models.ForeignKey(Tier, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    stripe_session_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.tier.name} - {self.status}"    