from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationTemplateViewSet, NotificationViewSet

router = DefaultRouter()
router.register(r'templates', NotificationTemplateViewSet, basename='templates')
router.register("notifications", NotificationViewSet, basename="notifications")

urlpatterns = [
    path('', include(router.urls)),
]