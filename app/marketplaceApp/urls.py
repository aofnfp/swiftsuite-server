from .views import Ebay, WooCommerce, listing_on_marketplace, save_product_before_listing_on_marketplace
from django.urls import path

urlpatterns = [
    path('get_auth_code/<str:market_name>/', Ebay.make_connection_to_get_auth_code, name='get_auth_code'),
    path('oauth/callback/<int:userid>/<str:market_name>/', Ebay.oauth_callback, name='oauth_callback'),
    path('refresh_connection/<int:userid>/<str:market_name>/', Ebay.refresh_connection_and_get_policy, name='refresh_connection'),
    path('get_ebay_store_id/', Ebay.get_ebay_user_id, name='get_ebay_store_id'),
    path('complete_enrolment_or_update/<int:userid>/<str:market_name>/', Ebay.complete_enrolment_or_update, name='complete_enrolment_or_update'),
    path('get_enrolment_detail/<int:userid>/<str:market_name>/', Ebay.get_enrolment_detail , name='get_enrolment_detail'),
    path('get_product_to_list_details/<int:userid>/<str:market_name>/<int:prod_id>/', Ebay.get_product_to_list_detail, name='get_product_to_list_details'),
    path('get_item_leaf_category/<int:userid>/<str:market_name>/<int:category_id>/', Ebay.get_leaf_category_id, name='get_item_leaf_category'),
    path('get_item_specific_fields/<int:userid>/<str:market_name>/<int:leaf_category_id>/', Ebay.get_item_specifics_fields, name='get_item_specific_fields'),
    path('upload_product_image/<int:productid>/<str:product_name>/<int:userid>/', Ebay.upload_product_image, name='upload_product_image'),
    path('upload_multiple_product_image/<int:productid>/<str:product_name>/<int:userid>/', Ebay.upload_multiple_product_images, name='upload_multiple_product_image'),
    path('get_uploaded_images/<int:productid>/<str:product_name>/<int:userid>/', Ebay.get_uploaded_image, name='get_uploaded_images'),
    path('delete_uploaded_images/<str:image_name>/<int:image_id>/', Ebay.delete_uploaded_image, name='delete_uploaded_images'),
    
    path('marketplace_product_listing/<int:userid>/<str:market_name>/<str:category_id_or_name>/', listing_on_marketplace, name='marketplace_product_listing'),
    path('save_product_before_listing/<int:userid>/<str:category_id_or_name>/', save_product_before_listing_on_marketplace, name='save_product_before_listing'),
    
    path('woocommerce_enrolment/<int:userid>/', WooCommerce.woocommerce_enrollment, name='woocommerce_enrolment'),
    path('test_woocommerce_connection/<int:userid>/<str:market_name>/', WooCommerce.test_woocommerce_connection, name='test_woocommerce_connection'),
    path('update_woocommerce_enrolment/<int:userid>/<str:market_name>/', WooCommerce.update_woocommerce_enrolment, name='update_woocommerce_enrolment'),
    path('get_product_category/<int:userid>/<str:market_name>/', WooCommerce.get_product_category, name='get_product_category'),
]
