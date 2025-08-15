from . import views 
from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register('vendor', views.VendorsViewSet, basename='vendor')

urlpatterns = [
    path('', include(router.urls)),
    path('upload-data/', views.UploadVendorData.as_view(), name='upload_data'),
]
