from rest_framework import serializers
from .models import Vendors

class VendorsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendors
        fields = '__all__'
        
class SupplierDetailSerializer(serializers.Serializer):
    api_access_id = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    api_access_key = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    
    username = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    password = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True, write_only=True)
    pos = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True) 
    
    ftp_username = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    ftp_password = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True, write_only=True)
    host = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    
    