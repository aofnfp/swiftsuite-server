from .views import OrderEbay as eb_view
from django.urls import path

urlpatterns = [
    
    path('get_ebay_orders/<int:userid>/<int:page_number>/<int:num_per_page>/', eb_view.get_product_ordered, name='get_ebay_orders'),
    path('get_ordered_item_details/<int:userid>/<str:market_name>/<str:ebayorderid>/', eb_view.get_ordered_item_details, name='get_ordered_item_details'),
    path('cancel_ordered_item/<int:userid>/<str:market_name>/<str:ebayorderid>/', eb_view.cancel_order_from_ebay, name='cancel_ordered_item'),
    path('sync_ordered_item/', eb_view.sync_ebay_order_with_local, name='sync_ordered_item'),
    
]
