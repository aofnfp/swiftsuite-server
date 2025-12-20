from rest_framework import serializers
from .models import InventoryModel

class InventoryModelUpdateSerializer(serializers.ModelSerializer):
	marketplace_name = serializers.CharField(required=False, allow_blank=True)

	class Meta:
		model = InventoryModel
		exclude = ('id', 'user')

	def update(self, instance, validated_data):
		validated_data.pop('user_id', None)
		return super().update(instance, validated_data)
	

class MappingToVendorSerializer(serializers.Serializer):
	vendor_name = serializers.CharField(required=True)
	product_objects = serializers.ListField(
        child=serializers.DictField(),
        required=True
    )


class SearchQuerySerializer(serializers.Serializer):
	search_query = serializers.CharField(required=True, allow_blank=False)