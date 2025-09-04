from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from .models import Vendors
from rest_framework import status
from .serializers import (
    VendorsSerializer
    )
from .permission import IsSuperUser
from rest_framework.parsers import MultiPartParser, FormParser
from .utils import get_suppliers_for_vendor
from django.core.exceptions import ObjectDoesNotExist
import uuid
from django.core.cache import cache
from .tasks import process_vendor_data
from django.shortcuts import get_object_or_404


class VendorsViewSet(ModelViewSet):
    queryset = Vendors.objects.all()
    serializer_class = VendorsSerializer
    permission_classes = [IsSuperUser]
    parser_classes = (MultiPartParser, FormParser) 
    
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
   
