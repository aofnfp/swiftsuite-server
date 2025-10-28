from django.urls import path
from .views import generate_report, sales_inventory_report

urlpatterns = [
    path('get_ebay_report/<int:userId>/<str:date_range>/', generate_report, name='get_ebay_report'),
    path('get_sales_inventory_report/<int:userId>/', sales_inventory_report, name='get_sales_inventory_report'),
]