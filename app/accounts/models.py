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
    def can_create_subaccount(self):
        if self.is_subaccount:
           return False
        if not self.tier:
            return False
        return self.subaccounts.count() < self.tier.max_subaccounts

class OneTimePassword(models.Model):

   user = models.OneToOneField(User, on_delete = models.CASCADE)
   code = models.CharField(max_length = 6, unique = True)

   def __str__(self):
       return f"{self.user.first_name}--passcode"
       
       
       
class UploadedUserProfileImage(models.Model):
    image_url = models.ImageField(upload_to='UserProfileImage/', null=False, unique=False)
    image_name = models.CharField(max_length=100, null=False, unique=False)
    uploaded_date= models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, unique=False, null=False)
    
    
    
class SubAccountPermissions(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='permissions')
    can_view = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)

    def __str__(self):
        return f"Permissions for {self.user.email}"
    
    
class Tier(models.Model):
    TIER_CHOICES = (
        (1, 'Tier 1'),
        (2, 'Tier 2'), 
        (3, 'Tier 3')
    )
    
    name = models.CharField(max_length=50, unique=True)
    tier = models.CharField(choices=TIER_CHOICES, max_length=20, null=True, blank=True)
    max_subaccounts = models.PositiveIntegerField(default=0)
    max_integrations = models.PositiveIntegerField(default=0)
    max_sku = models.PositiveIntegerField(default=0)
    max_orders = models.PositiveIntegerField(default=0)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Subscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tier_subscription')
    tier = models.ForeignKey(Tier, on_delete=models.CASCADE)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

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