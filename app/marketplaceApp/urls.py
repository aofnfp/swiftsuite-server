from .views import Ebay as view
from django.urls import path

urlpatterns = [
    path('get_auth_code/<str:market_name>/', view.make_connection_to_get_auth_code, name='get_auth_code'),
    path('oauth/callback/<int:userid>/<str:market_name>/', view.oauth_callback, name='oauth_callback'),
    path('refresh_connection/<int:userid>/<str:market_name>/', view.refresh_connection_and_get_policy, name='refresh_connection'),
    path('complete_enrolment_or_update/<int:userid>/<str:market_name>/', view.complete_enrolment_or_update, name='complete_enrolment_or_update'),
    path('get_enrolment_detail/<int:userid>/<str:market_name>/', view.get_enrolment_detail , name='get_enrolment_detail'),
    path('get_product_to_list_details/<int:userid>/<str:market_name>/<int:prod_id>/', view.get_product_to_list_detail, name='get_product_to_list_details'),
    path('get_item_leaf_category/<int:userid>/<str:market_name>/<int:category_id>/', view.get_leaf_category_id, name='get_item_leaf_category'),
    path('get_item_specific_fields/<int:userid>/<str:market_name>/<int:leaf_category_id>/', view.get_item_specifics_fields, name='get_item_specific_fields'),
    path('marketplace_product_listing/<int:userid>/<str:market_name>/<int:leaf_category_id>/', view.product_listing_to_ebay, name='marketplace_product_listing'),
    path('save_product_before_listing/<int:userid>/<int:leaf_category_id>/', view.save_product_before_listing, name='save_product_before_listing'),
    path('get_ebay_store_id/', view.get_ebay_user_id, name='get_ebay_store_id'),
    path('upload_product_image/<int:productid>/<str:product_name>/<int:userid>/', view.upload_product_image, name='upload_product_image'),
    path('get_uploaded_images/<int:productid>/<str:product_name>/<int:userid>/', view.get_uploaded_image, name='get_uploaded_images'),
    path('delete_uploaded_images/<str:image_name>/<int:image_id>/', view.delete_uploaded_image, name='delete_uploaded_images'),
    
]
