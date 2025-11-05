
from django.contrib import admin
from django.urls import path, include, re_path
from accounts.views import landingPage
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path("admin/", admin.site.urls),
    re_path(r'^accounts/', include("accounts.urls")),
    re_path(r'^inventoryApp/', include("inventoryApp.urls")),
    re_path(r'^marketplaceApp/', include("marketplaceApp.urls")),
    re_path(r'inventoryApp/', include("inventoryApp.urls")),
    re_path(r'orderApp/', include("orderApp.urls")),
    re_path(r'reportApp/', include("reportApp.urls")),
    path('', landingPage, name="home"),
    path('api/v2/', include('vendorActivities.urls')),
    path('api/v2/', include('vendorEnrollment.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/docs/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
