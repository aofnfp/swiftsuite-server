from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from .models import Vendors
from rest_framework import status
from .serializers import (
    VendorsSerializer,
    VendorRequestSerializer
    )
from .permission import IsSuperUser
from rest_framework.parsers import MultiPartParser, FormParser
from .utils import get_suppliers_for_vendor
import uuid
from django.core.cache import cache
from .tasks import process_vendor_data
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from vendorActivities.payment_utils import create_vendor_checkout_session
from accounts.models import Payment
from rest_framework_extensions.cache.decorators import cache_response


class VendorsViewSet(ModelViewSet):
    queryset = Vendors.objects.all()
    serializer_class = VendorsSerializer
    permission_classes = [IsSuperUser]
    parser_classes = (MultiPartParser, FormParser) 
    
    
    def get_queryset(self):
        queryset = Vendors.objects.all().order_by('-created_at')
        queryset = queryset.exclude(integration_type='requested', available=False)
        return queryset
    
    @cache_response()
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
        
class UploadVendorData(APIView):
    permission_classes = [IsSuperUser]
    
    def get(self, request, vendor_id):    
        vendor = get_object_or_404(Vendors, id = vendor_id)
        supplier = None
        task_id = str(uuid.uuid4())
        
        if vendor.name == 'fragrancex':
            supplier = (vendor.name, vendor.api_access_id, vendor.api_access_key)
            
        elif vendor.name == 'rsr':
            supplier = (vendor.name, vendor.username, vendor.password, vendor.pos)
            
        else:
            supplier = get_suppliers_for_vendor(vendor.name, vendor.host, vendor.ftp_username, vendor.ftp_password)

        process_vendor_data.delay(supplier, task_id, vendor.id)
        return Response({
            'task_id': task_id,
            'message': 'Vendor processing has started in the background'
        }, status=status.HTTP_200_OK)
            

class CheckTaskProgress(APIView):
    def get(self, request):
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response({'error': 'Task ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        progress = cache.get(f"upload_progress_{task_id}")
        if progress is None:
            return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'task_id': task_id, 'progress': progress}, status=status.HTTP_200_OK)
   


class VendorRequestView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = VendorRequestSerializer(data=request.data , context={'request': request})
        serializer.is_valid(raise_exception=True)
        vendor = serializer.save()
        
        message = (
            "Vendor request submitted successfully."
            if vendor.request_type == 'regular'
            else "Force integration request submitted. Payment pending."
        )

        return Response({
            "message": message,
            "vendor": VendorRequestSerializer(vendor).data
        }, status=status.HTTP_201_CREATED)
    

class VendorPaymentInitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, vendor_id):
        vendor = get_object_or_404(Vendors, id=vendor_id, requested_by=request.user)

        if vendor.request_type != 'force':
            return Response({"error": "This vendor does not require payment."}, status=400)

        if Payment.objects.filter(vendor=vendor, status='paid').exists():
            return Response({"error": "Payment has already been completed for this vendor."}, status=400)

        session = create_vendor_checkout_session(request, vendor)
        
        # Return payment URL for frontend to redirect
        if isinstance(session, Response):
            # Handle Stripe creation failure
            return session

        # Return payment URL for frontend to redirect
        return Response({
            "checkout_url": session.url,
            "session_id": session.id
        }, status=status.HTTP_200_OK)
        
        