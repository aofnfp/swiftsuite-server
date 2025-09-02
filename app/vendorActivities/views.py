from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from .models import Vendors
from rest_framework import status
from .serializers import (
    VendorsSerializer,
    SupplierDetailSerializer
    )
from .permission import IsSuperUser
from rest_framework.parsers import MultiPartParser, FormParser
from .utils import get_suppliers_for_vendor
from django.core.exceptions import ObjectDoesNotExist
import uuid
from django.core.cache import cache
from .tasks import process_vendor_data


class VendorsViewSet(ModelViewSet):
    queryset = Vendors.objects.all()
    serializer_class = VendorsSerializer
    permission_classes = [IsSuperUser]
    parser_classes = (MultiPartParser, FormParser) 
    
class UploadVendorData(APIView):
    permission_classes = [IsSuperUser]
    
    def post(self, request):
        vendor_name = request.query_params.get('vendor_name')
        if not vendor_name:
            return Response({'error': 'Vendor name is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            vendor_info = Vendors.objects.get(name=vendor_name)
        except ObjectDoesNotExist:
            return Response({'error': 'Vendor not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = SupplierDetailSerializer(data = request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        payload = serializer.validated_data
        supplier = None
        task_id = str(uuid.uuid4())
        
        if vendor_info and not vendor_info.has_data:
            if vendor_name == 'fragrancex':
                apiAccessId = payload.get('api_access_id')
                apiAccessKey = payload.get('api_access_key')
                supplier = (vendor_name, apiAccessId, apiAccessKey)
                
            elif vendor_name == 'rsr':
                username = payload.get('username')
                password = payload.get('password')
                pos = payload.get('pos')
                supplier = ('rsr', username, password, pos)
                
            else:
                ftp_host = payload.get('host')
                ftp_user = payload.get('ftp_username')
                ftp_password = payload.get('ftp_password')
                supplier = get_suppliers_for_vendor(vendor_name, ftp_host, ftp_user, ftp_password)

            process_vendor_data.delay(supplier, task_id, vendor_info.id)
            return Response({
                'task_id': task_id,
                'message': 'Vendor processing has started in the background'
            }, status=status.HTTP_200_OK)
            
        else:
            return Response({'message': 'Vendor data already loaded'}, status=status.HTTP_400_BAD_REQUEST)
                
                
        

class CheckTaskProgress(APIView):
    def get(self, request):
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response({'error': 'Task ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        progress = cache.get(f"upload_progress_{task_id}")
        if progress is None:
            return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'task_id': task_id, 'progress': progress}, status=status.HTTP_200_OK)
   
