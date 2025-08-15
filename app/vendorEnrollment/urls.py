from django.urls import path, include, re_path
from . import views as vw
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'enrollment', vw.EnrollmentViewSet, basename='enrollment')
router.register(r'vendor-account', vw.AccountViewset, basename='vendor-account')


urlpatterns = [
    path('', include(router.urls)),
    path('vendor-test/', vw.VendorTestView.as_view()),
    path('update-enrollment/<str:identifier>/',vw.update_enrolment, name='update-enrolment'),
    path('delete-enrollment/<str:identifier>/', vw.delete_enrolment, name='delete-enrolment'),
    path('view-enrollment-with-identifier/<str:identifier>/', vw.getEnrollmentWithIdentifier, name = 'view-enrolment-with-identifier'),
    
    re_path(r'^catalogue-fragrancex/(?P<pk>\d+)(?:/(?P<identifier>[\w-]+))?/$', vw.CatalogueFragrancexView.as_view(), name='catalogue-fragrancex'),
    re_path(r'^catalogue-zanders/(?P<pk>\d+)(?:/(?P<identifier>[\w-]+))?/$', vw.CatalogueZandersView.as_view(), name='catalogue-zanders'),
    re_path(r'^catalogue-lipsey/(?P<pk>\d+)(?:/(?P<identifier>[\w-]+))?/$', vw.CatalogueLipseyView.as_view(), name='catalogue-lipsey'),
    # re_path(r'^catalogue-ssi/(?P<pk>\d+)(?:/(?P<identifier>[\w-]+))?/$', CatalogueSsiView.as_view(), name='catalogue-ssi'),
    re_path(r'^catalogue-cwr/(?P<pk>\d+)(?:/(?P<identifier>[\w-]+))?/$', vw.CatalogueCwrView.as_view(), name='catalogue-cwr'),
    re_path(r'^catalogue-rsr/(?P<pk>\d+)(?:/(?P<identifier>[\w-]+))?/$', vw.CatalogueRsrView.as_view(), name='catalogue-rsr'),
    path('catalogue-all/<int:pk>/', vw.AllCatalogueView.as_view(), name='catalogue-all'),
    
    path('add-to-product/<int:userid>/<int:product_id>/<str:vendor_name>/', vw.AddProductView.as_view(), name='add-to-product'),
    path('add-to-product/<int:userid>/<int:product_id>/<str:vendor_name>/<str:identifier>/', vw.AddProductView.as_view(), name='add-to-product'),
    path('delete-product/<int:productId>/', vw.removeProduct, name='delete-product'),
    path('view-all-products/', vw.ViewAllProducts.as_view(), name='view-all-products'),
    
    path('account-enrollments/', vw.UserAccountEnrollmentsView.as_view(), name='account-enrollments'),
    path('all-enrolled-vendors/', vw.allEnrolledVendors, name='all-enrolled-vendors'),
]
