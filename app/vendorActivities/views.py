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
from .utils import VendorActivity, get_suppliers_for_vendor
from django.core.exceptions import ObjectDoesNotExist
import threading, uuid, time
from django.core.cache import cache
from .tasks import process_rsr_in_background


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
        
        process_vendor = False
        pull = VendorActivity()
        payload = serializer.validated_data
        
        if vendor_info and not vendor_info.has_data:
            if vendor_name == 'fragrancex':
                apiAccessId = payload.get('api_access_id')
                apiAccessKey = payload.get('api_access_key')
                supplier = (vendor_name, apiAccessId, apiAccessKey)
                process_vendor = pull.main(supplier)
            
            elif vendor_name == 'rsr':
                task_id = str(uuid.uuid4())
                threading.Thread(target=process_rsr_in_background, args=(payload, task_id, vendor_info.id)).start()
                return Response({
                    'task_id': task_id,
                    'message': 'RSR processing started in the background'
                }, status=status.HTTP_200_OK)
                
            else:
                ftp_host = payload.get('host')
                ftp_user = payload.get('ftp_username')
                ftp_password = payload.get('ftp_password')
                suppliers = get_suppliers_for_vendor(vendor_name, ftp_host, ftp_user, ftp_password)
                process_vendor = pull.main(suppliers)
            
        else:
            return Response({'message': 'Vendor data already loaded'}, status=status.HTTP_400_BAD_REQUEST)
                
                
        if process_vendor == True:
            pull.removeFile()
            vendor_info.has_data = True
            vendor_info.save()
            return Response({'message': 'Vendor data loaded successfully'}, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'Failed to load vendor data'}, status=status.HTTP_400_BAD_REQUEST)
        

class CheckTaskProgress(APIView):
    def get(self, request):
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response({'error': 'Task ID is required'}, status=400)
        
        progress = cache.get(f"upload_progress_{task_id}")
        if progress is None:
            return Response({'error': 'Task not found'}, status=404)
        
        return Response({'task_id': task_id, 'progress': progress})   
