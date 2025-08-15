from .views import *
from django.urls import path,re_path


urlpatterns = [
    path('vendor-enrolment/',VendoEnronmentView.as_view(), name='vendor-enrolment'),
    path('vendor-enrolment-test/',VendorEnrolmentTestView.as_view(), name='vendor-enrolment-test'),
    path('update-vendor-enrolment/<str:identifier>/',update_vendor_enrolment, name='update-vendor-enrolment'),
    path('delete-vendor-enrolment/<str:identifier>/',delete_vendor_enrolment, name='delete-vendor-enrolment'),
    path('delete-vendor-data/<str:vendor_name>/', delete_vendorData, name = 'delete-vendor-data'),
    path('view-enrolment-with-identifier/<str:identifier>/', getEnrolmentWithIdentifier, name = 'view-enrolment-with-identifier'),

    re_path(r'^catalogue-fragrancex/(?P<pk>\d+)(?:/(?P<identifier>[\w-]+))?/$',CatalogueFragrancexView.as_view(), name='catalogue-fragrancex'),
    re_path(r'^catalogue-zanders/(?P<pk>\d+)(?:/(?P<identifier>[\w-]+))?/$',CatalogueZandersView.as_view(), name='catalogue-zanders'),
    re_path(r'^catalogue-lipsey/(?P<pk>\d+)(?:/(?P<identifier>[\w-]+))?/$',CatalogueLipseyView.as_view(), name='catalogue-lipsey'),
    re_path(r'^catalogue-ssi/(?P<pk>\d+)(?:/(?P<identifier>[\w-]+))?/$',CatalogueSsiView.as_view(), name='catalogue-ssi'),
    re_path(r'^catalogue-cwr/(?P<pk>\d+)(?:/(?P<identifier>[\w-]+))?/$', CatalogueCwrView.as_view(), name='catalogue-cwr'),
    re_path(r'^catalogue-fragrancex/(?P<pk>\d+)(?:/(?P<identifier>[\w-]+))?/$', CatalogueCwrView.as_view(), name='catalogue-fragrancex'),
    re_path(r'^catalogue-rsr/(?P<pk>\d+)(?:/(?P<identifier>[\w-]+))?/$', CatalogueRsrView.as_view(), name='catalogue-rsr'),
    path('catalogue-all/<int:pk>/',AllCatalogueView.as_view(), name='catalogue-all'),
    

    path('add-to-product/<int:userid>/<int:product_id>/<str:vendor_name>/<str:vendor_identifier>/', AddProductView.as_view(), name='add-to-product'),
    path('add-to-product/<int:userid>/<int:product_id>/<str:vendor_name>/', AddProductView.as_view(), name='add-to-product'),
    path('view-all-products/<int:userid>/', ViewAllProducts.as_view(), name='view-all-products'),
    path('delete-product/<int:productId>/', removeProduct, name='delete-product'),

    path('all-identifiers/', ViewAllIdentifiers.as_view(), name='all-identifiers'),
    path('vendor-identifiers/<str:vendor_name>/', VendorIdentifiers.as_view(), name='vendor-identifiers'),
    path('all-vendor-enrolled/', AllVendorEnrolled.as_view(), name='all-vendor-enrolled'),

    path('track-progress/<str:task_id>/', UploadProgressView.as_view(), name="track-progress"),


]
