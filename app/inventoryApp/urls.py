from .views import MarketInventory, update_product_on_marketplace, WooCommerceInventory, General_operations

from django.urls import path

urlpatterns = [
    path('get_all_inventory_items/<int:userid>/<int:page_number>/<int:num_per_page>/', MarketInventory.get_all_inventory_items, name='get_all_inventory_items'),
    path('get_all_saved_inventory_items/<int:userid>/<int:page_number>/<int:num_per_page>/', MarketInventory.get_all_saved_inventory_items, name='get_all_saved_inventory_items'),
    path('get_saved_product_for_listing/<int:inventoryid>/', MarketInventory.get_saved_product_for_listing, name='get_saved_product_for_listing'),
    path('delete_product_from_inventory/<int:inventoryid>/', MarketInventory.delete_product_from_inventory, name='delete_product_from_inventory'),
    path('update_item_details_on_marketplace/<int:userid>/<str:market_name>/<int:inventory_id>/', update_product_on_marketplace, name='update_item_details_on_marketplace'),
    path('end_and_delete_product_from_ebay/<int:userid>/<int:inventoryid>/', MarketInventory.end_delete_product_from_ebay, name='end_and_delete_product_from_ebay'),
    path('test_api_function/<int:userid>/<int:item_id>/', MarketInventory.function_to_test_api, name='test_api_function'),

    path('get_all_unmapped_items/<int:userid>/<int:page_number>/<int:num_per_page>/', General_operations.get_unmapped_listing_items, name='get_all_unmapped_items'),
    path('map_inventory_item_to_vendor/<int:userid>/<str:market_name>/', General_operations.map_inventory_item_to_vendor, name='map_inventory_item_to_vendor'),
    path('get_unmapped_items_details/<int:userid>/<int:inventoryid>/', General_operations.get_unmapped_product_details, name='get_unmapped_items_details'),
    path('search_query_inventory_items/<int:userid>/<int:page_number>/<int:num_per_page>/', General_operations.search_query_inventory_items, name='search_query_inventory_items'),
    path('search_query_unmapped_inventory_items/<int:userid>/<int:page_number>/<int:num_per_page>/', General_operations.search_query_unmapped_inventory_items, name='search_query_unmapped_inventory_items'),
    path('get_all_marketplaces_enrolled/<int:userid>/', General_operations.get_all_marketplaces_enrolled, name='get_all_marketplaces_enrolled'),
    path('get_all_vendor_enrolled/<int:userid>/', General_operations.get_all_vendor_enrollment, name='get_all_vendor_enrolled'),
    path('manually_download_inventory_items/', General_operations.manually_download_item_from_marketplace, name='manually_download_inventory_items'),
]
