from . import views 
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from vendorActivities.payment_utils import stripe_webhook

router = DefaultRouter()
router.register('vendor', views.VendorsViewSetUser, basename='vendor')
router.register('vendor-admin', views.VendorsViewSetAdmin, basename='vendor-admin')

urlpatterns = [
    path('', include(router.urls)),
    path('upload-data/<int:vendor_id>/', views.UploadVendorData.as_view(), name='upload_data'),
    path('vendor-request/', views.VendorRequestView.as_view(), name='vendor_request'),
    path('init-payment/<int:vendor_id>/', views.VendorPaymentInitView.as_view(), name='initiate_payment'),
    path('payment-webhook/', stripe_webhook, name='payment_webhook'),
]
