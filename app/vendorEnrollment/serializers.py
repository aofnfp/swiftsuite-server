from rest_framework import serializers
from .models import Enrollment, FragrancexUpdate,LipseyUpdate, CwrUpdate, RsrUpdate, ZandersUpdate, Account, Generalproducttable
from vendorActivities.models import Vendors, Fragrancex, Lipsey, Cwr, Rsr, Zanders
from accounts.models import User
from django.db import transaction
from vendorActivities.serializers import VendorsSerializer
from django.db import IntegrityError
from .utils import VendorDataMixin


class VendorTestSerializer(serializers.ModelSerializer):
    vendor = serializers.PrimaryKeyRelatedField(queryset=Vendors.objects.all())
    class Meta:
        model = Account
        fields = [
            'vendor',
            'ftp_username', 
            'ftp_password',
            'host',
            'apiAccessId',
            'apiAccessKey',
            'Username',
            'Password',
            'POS'
        ]

        extra_kwargs = {field: {'required': False} for field in fields}

class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = '__all__'
        extra_kwargs = {field.name: {'required': False} for field in Account._meta.get_fields()}

        
class EnrollmentSerializer(VendorDataMixin, serializers.ModelSerializer):
    vendor = serializers.PrimaryKeyRelatedField(queryset=Vendors.objects.all())
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all(), required=False)
    account_data = serializers.JSONField(write_only=True, required=False)
    class Meta:
        model = Enrollment
        fields = '__all__'
        extra_kwargs = {field.name: {'required': False} for field in Enrollment._meta.get_fields()}
        
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['user'] = request.user
        
        account_data = validated_data.pop('account_data', None)
        account = validated_data.get('account')
        vendor = validated_data.get('vendor')
        
        if not vendor:
            raise serializers.ValidationError({'error': 'Vendor is required'})

        config = self.get_vendor_config(vendor.name)
        model = config['model']
        update_model = config['update_model']
        mpn_field = config['mpn_field']

        with transaction.atomic():
            if account is None:
                if account_data is None:
                    raise serializers.ValidationError({'error': 'Either account ID or account_data is required.'})
                try:
                    account = Account.objects.create(user=request.user, vendor=vendor, **account_data)
                    validated_data['account'] = account
                except IntegrityError:
                    raise serializers.ValidationError({'error': 'An account with this name already exists.'})

            enrollment = Enrollment.objects.create(**validated_data)

            if not update_model.objects.filter(account=account).exists():
                filtered_data = [
                    item for item in model.objects.all()
                    if self.product_matches_filters(item, enrollment, config['vendor_name'])
                ]
                updates = [
                    update_model(
                        product=item,
                        account=account,
                        vendor=vendor,
                        enrollment=enrollment,
                        sku=getattr(item, 'sku', None),
                        mpn=getattr(item, mpn_field, None),
                        upc=getattr(item, 'upc', None),
                    )
                    for item in filtered_data
                ]
                update_model.objects.bulk_create(updates)

        return enrollment

class FragrancexSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fragrancex
        fields = '__all__'

class FragrancexUpdateSerializer(serializers.ModelSerializer):
    product = FragrancexSerializer()

    class Meta:
        model = FragrancexUpdate
        fields = '__all__'

class CwrSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cwr
        fields = '__all__'

class CwrUpdateSerializer(serializers.ModelSerializer):
    product = CwrSerializer()

    class Meta:
        model = CwrUpdate
        fields = '__all__'
       
class LipseySerializer(serializers.ModelSerializer):
    class Meta:
        model = Lipsey
        fields = '__all__'

class LipseyUpdateSerializer(serializers.ModelSerializer):
    product = LipseySerializer()

    class Meta:
        model = LipseyUpdate
        fields = '__all__'

class ZandersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Zanders
        fields = '__all__'

class ZandersUpdateSerializer(serializers.ModelSerializer):
    product = ZandersSerializer()

    class Meta:
        model = ZandersUpdate
        fields = '__all__'
        
class RsrSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rsr
        fields = '__all__'

class RsrUpdateSerializer(serializers.ModelSerializer):
    product = RsrSerializer()

    class Meta:
        model = RsrUpdate
        fields = '__all__'

class GeneralProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Generalproducttable
        fields = '__all__'
        
class AccountWithEnrollmentsSerializer(serializers.ModelSerializer):
    enrollments = serializers.SerializerMethodField()
    vendor = VendorsSerializer()

    class Meta:
        model = Account
        fields = '__all__' 

    def get_enrollments(self, obj):
        enrollments = obj.enrollments.all()
        return EnrollmentSerializer(enrollments, many=True).data