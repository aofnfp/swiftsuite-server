from rest_framework import serializers
from .models import Vendors
from accounts.tasks import send_normal_email
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


class VendorRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendors
        fields =  fields = [
            'id', 'name', 'address_street1', 'address_street2',
            'city', 'state', 'zip_code', 'country',
            'integration_type', 'request_type',
            'api_details', 'host', 'ftp_username', 'ftp_password'
        ]
        read_only_fields = ['integration_type']
        
    def validate_request_type(self, value):
        if value not in ['regular', 'force']:
            raise serializers.ValidationError("Request type must be 'regular' or 'force'.")
        return value
    
    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['integration_type'] = 'requested'
        validated_data['requested_by'] = user

        vendor = Vendors.objects.create(**validated_data)
        context_user = {
            'user': user.id,
            'vendor': vendor.id,
        }
        send_normal_email.delay(context_user, file='user_notification.html')
        context_admin = {
            'vendor': vendor.id,
            'to_email': 'support@swiftsuite.app'
        }
        send_normal_email.delay(context_admin, file='admin_notification.html')
        
        return vendor