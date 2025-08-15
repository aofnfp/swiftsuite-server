
from django.contrib import admin
from django.urls import path, include, re_path
from accounts.views import landingPage

urlpatterns = [
    path("admin/", admin.site.urls),
    re_path(r'^accounts/', include("accounts.urls")),
    re_path(r'^vendor/', include("vendorApp.urls")),
    re_path(r'^inventoryApp/', include("inventoryApp.urls")),
    re_path(r'^marketplaceApp/', include("marketplaceApp.urls")),
    re_path(r'inventoryApp/', include("inventoryApp.urls")),
    re_path(r'orderApp/', include("orderApp.urls")),
    path('', landingPage, name="home"),
]
