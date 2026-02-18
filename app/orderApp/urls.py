from .views import OrderEbay as eb_view, OrderSyncView
from django.urls import path, include
from .fragranceX_order import place_order_fragrancex, getTracking_fragranceX
from .rsr_order import place_order_rsr, check_order_rsr, push_tracking, get_shipping_fulfillment
from rest_framework import routers

router = routers.DefaultRouter()
router.register(r'orders', OrderSyncView, basename='order')

urlpatterns = [
    
    path('get_ebay_orders/<int:userid>/<int:page_number>/<int:num_per_page>/', eb_view.get_product_ordered, name='get_ebay_orders'),
    path('get_ordered_item_details/<int:userid>/<str:market_name>/<str:ebayorderid>/', eb_view.get_ordered_item_details, name='get_ordered_item_details'),
    path('cancel_ordered_item/<int:userid>/<str:market_name>/<str:ebayorderid>/', eb_view.cancel_order_from_ebay, name='cancel_ordered_item'),
    path('download_order_manually/<int:userid>/', eb_view.sync_ebay_order_with_local_manually, name='download_order_manually'),

    path('place_order_fragrancex/<str:market_name>/<str:orderid>/', place_order_fragrancex, name='place_order_fragrancex'),
    path('get_tracking_fragranceX/<str:orderId>/', getTracking_fragranceX, name='get_tracking_fragranceX'),
    path('place_order_rsr/<str:market_name>/<str:orderid>/', place_order_rsr, name='place_order_rsr'),
    path('check_order_rsr/<str:market_name>/<str:orderid>/', check_order_rsr, name='check_order_rsr'),
    path('push_tracking_to_ebay/<str:order_id>/', push_tracking, name='push_tracking_to_ebay'),
    path('get_shipping_fulfillment/<str:order_id>/', get_shipping_fulfillment, name='get_shipping_fulfillment'),
    path('', include(router.urls)),
]
