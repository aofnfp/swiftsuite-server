from .views import OrderEbay as eb_view, OrderSyncView, PlaceOrderView, TrackOrderView, PushTrackingView, GetFulfillmentView
from django.urls import path, include
from .order_clients.fx_order import place_order_fragrancex, getTracking_fragranceX
from .order_clients.rsr_order import place_order_rsr, check_order_rsr, push_tracking, get_shipping_fulfillment
from rest_framework import routers

router = routers.DefaultRouter()
router.register(r'orders', OrderSyncView, basename='order')

urlpatterns = [
    
    path('get_ebay_orders/<int:userid>/<int:page_number>/<int:num_per_page>/', eb_view.get_product_ordered, name='get_ebay_orders'),
    path('get_ordered_item_details/<int:userid>/<str:market_name>/<str:ebayorderid>/', eb_view.get_ordered_item_details, name='get_ordered_item_details'),
    path('cancel_ordered_item/<int:userid>/<str:market_name>/<str:ebayorderid>/', eb_view.cancel_order_from_ebay, name='cancel_ordered_item'),
    path('download_order_manually/', eb_view.sync_ebay_order_with_local_manually, name='download_order_manually'),

    path('place_order_fragrancex/<str:market_name>/<str:orderid>/', place_order_fragrancex, name='place_order_fragrancex'),
    path('get_tracking_fragranceX/<str:orderId>/', getTracking_fragranceX, name='get_tracking_fragranceX'),
    path('place_order_rsr/<str:market_name>/<str:orderid>/', place_order_rsr, name='place_order_rsr'),
    path('check_order_rsr/<str:market_name>/<str:orderid>/', check_order_rsr, name='check_order_rsr'),
    path('push_tracking_to_ebay/<str:order_id>/', push_tracking, name='push_tracking_to_ebay'),
    path('get_shipping_fulfillment/<str:order_id>/', get_shipping_fulfillment, name='get_shipping_fulfillment'),


    path('place_order/<str:market_name>/<str:order_id>/', PlaceOrderView.as_view(), name='place_order'),
    path('track_order/<str:order_id>/', TrackOrderView.as_view(), name='track_order'),
    path('push_tracking/<str:order_id>/', PushTrackingView.as_view(), name='push_tracking'),
    path('get_fulfillment/<str:order_id>/', GetFulfillmentView.as_view(), name='get_fulfillment'),
    path('', include(router.urls)),
]
