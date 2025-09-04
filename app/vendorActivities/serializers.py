from rest_framework import serializers
from .models import Vendors

class VendorsSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        max_length=255, required=False, allow_null=True, allow_blank=True, write_only=True
    )
    ftp_password = serializers.CharField(
        max_length=255, required=False, allow_null=True, allow_blank=True, write_only=True
    )
    api_access_key = serializers.CharField(
        max_length=255, required=False, allow_null=True, allow_blank=True, write_only=True
    )
    class Meta:
        model = Vendors
        fields = '__all__'
        