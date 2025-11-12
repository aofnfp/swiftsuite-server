from .views import MarketInventory, update_product_on_marketplace
from .tasks import sync_ebay_items_with_local
from django.urls import path

urlpatterns = [
    path('syc_ebay_product_map/', sync_ebay_items_with_local, name='syc_ebay_product_map'),
    path('get_all_inventory_items/<int:userid>/<int:page_number>/<int:num_per_page>/', MarketInventory.get_all_inventory_items, name='get_all_inventory_items'),
    path('get_all_saved_inventory_items/<int:userid>/<int:page_number>/<int:num_per_page>/', MarketInventory.get_all_saved_inventory_items, name='get_all_saved_inventory_items'),
    path('get_all_unmapped_items/<int:userid>/', MarketInventory.get_unmapped_listing_items, name='get_all_unmapped_items'),
    path('get_saved_product_for_listing/<int:inventoryid>/', MarketInventory.get_saved_product_for_listing, name='get_saved_product_for_listing'),
    path('delete_product_from_inventory/<int:inventoryid>/', MarketInventory.delete_product_from_inventory, name='delete_product_from_inventory'),
    path('update_item_details_on_marketplace/<int:userid>/<str:market_name>/<int:inventory_id>/', update_product_on_marketplace, name='update_item_details_on_marketplace'),
    path('end_and_delete_product_from_ebay/<int:userid>/<int:inventoryid>/', MarketInventory.end_delete_product_from_ebay, name='end_and_delete_product_from_ebay'),
    path('test_api_function/<int:enrol_id>/<str:market_name>/', MarketInventory.function_to_test_api, name='test_api_function'),
]
