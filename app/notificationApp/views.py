from django.shortcuts import render
from .models import NotificationTemplate
from .serializers import NotificationTemplateSerializer, NotificationSerializer
from rest_framework import viewsets, filters
from vendorEnrollment.pagination import CustomOffsetPagination
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import Notification
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status



# Create your views here.

class NotificationTemplateViewSet(viewsets.ModelViewSet):
    queryset = NotificationTemplate.objects.all().order_by('-created_at')
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAdminUser]
    pagination_class = CustomOffsetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['category', 'header', 'body']
    ordering_fields = ['created_at', 'category']
    ordering = ['-created_at']
    
    
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """View to list all notifications for the authenticated user."""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]  
    pagination_class = CustomOffsetPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['sent_at', 'status']
    ordering = ['-sent_at']
    
    def get_queryset(self):
        user = self.request.user
        return Notification.objects.filter(recipient_user=user, channel = 'in_app').order_by('-sent_at')
    
    
    @action(detail=True, methods=["POST"])
    def read(self, request, pk=None):
        notification = self.get_object()

        if notification.read:
            return Response({"detail": "Already marked as read."})

        notification.read = True
        notification.save()

        return Response(
            {"detail": "Notification marked as read."},
            status=status.HTTP_200_OK
        )

    
    @action(detail=False, methods=["GET"])
    def unread_count(self, request):
        count = Notification.objects.filter(
            recipient_user=request.user, read=False, channel='in_app'
        ).count()

        return Response({"unread_count": count})