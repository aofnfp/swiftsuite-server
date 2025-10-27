from django.urls import path
from views import generate_report

urlpatterns = [
    path('get_ebay_report/<int:user_id>/<str:date_range>/', generate_report, name='get_ebay_report'),
]