from .views import MarketInventory as ebview
from django.urls import path

urlpatterns = [
    path('syc_ebay_product_map/', ebview.sync_ebay_items_with_local, name='syc_ebay_product_map'),
    path('get_all_inventory_items/<int:userid>/<int:page_number>/<int:num_per_page>/', ebview.get_all_inventory_items, name='get_all_inventory_items'),
    path('get_all_saved_inventory_items/<int:userid>/<int:page_number>/<int:num_per_page>/', ebview.get_all_saved_inventory_items, name='get_all_saved_inventory_items'),
    path('get_all_unmapped_items/<int:userid>/', ebview.get_unmapped_ebay_listing, name='get_all_unmapped_items'),
    path('get_saved_product_for_listing/<int:inventoryid>/', ebview.get_saved_product_for_listing, name='get_saved_product_for_listing'),
    path('delete_product_from_inventory/<int:inventoryid>/', ebview.delete_product_from_inventory, name='delete_product_from_inventory'),
    path('update_ebay_item_details/<int:inventory_id>/<int:userId>/', ebview.update_item_on_ebay, name='update_ebay_item_details'),
    path('end_and_delete_product_from_ebay/<int:userid>/<int:inventoryid>/', ebview.end_delete_product_from_ebay, name='end_and_delete_product_from_ebay'),
    path('test_api_function/', ebview.function_to_test_api, name='test_api_function'),
]
