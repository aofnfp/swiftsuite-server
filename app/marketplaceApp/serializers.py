from rest_framework import serializers
from .models import MarketplaceEnronment, AuthorizationCode, UploadedProductImage
from inventoryApp.models import InventoryModel

class MarketplaceEnrolSerializer(serializers.ModelSerializer):
	marketplace_name = serializers.CharField(required=False, allow_blank=True)

	class Meta:
		model = MarketplaceEnronment
		exclude = ('_id', 'user', 'access_token', 'refresh_token')

	def update(self, instance, validated_data):
		validated_data.pop('user_id', None)
		return super().update(instance, validated_data)
	
class GetAuthCodeSerializer(serializers.ModelSerializer):
	class Meta:
		model = AuthorizationCode
		fields = [
			"authorization_code"
		]

class ItemListingToEbaySerializer:
    
	def generate_item_specifics_serializer(item_specifics):
		# Create a dictionary for dynamic serializer fields
		serializer_fields = {}
		model_class = []
		item_specifics_name = []
		valid_choices_field = {}
		is_required = []
		# Create a ModelSerializer class for the model fields
		class ModelSerializer(serializers.ModelSerializer):
			class Meta:
				model = InventoryModel
				exclude = [
					'id',
					'item_specific_fields',
					'market_item_id',
					'user',
				]

		# Extract model fields (excluding the ones already present in eBay item specifics)
		for field_name, field_instance in ModelSerializer().get_fields().items():
			if field_name not in serializer_fields:
				serializer_fields[field_name] = field_instance
				model_class.append(field_name)

		# Handle dynamic fields from eBay item specifics
		for aspect in item_specifics:
			aspect_name = aspect['localizedAspectName']
			options = aspect.get('aspectValues', [])
			if aspect.get('aspectConstraint', {}).get('aspectUsage') == 'REQUIRED':
				is_required.append(aspect_name)
			
			# Skip if this field is already in the model fields to avoid duplication
			if hasattr(model_class, aspect_name):
				continue
			
			# If there are predefined options, use ChoiceField
			if options:
				choices = [(opt['localizedValue'], opt['localizedValue']) for opt in options]
			    # Store valid choices separately for reference
				valid_choices_field[aspect_name] = [opt['localizedValue'] for opt in options]
			    # Use CharField instead of ChoiceField to allow custom values
				serializer_fields[aspect_name] = serializers.CharField(
                    required=False,
                    allow_blank=True
                )
				item_specifics_name.append(aspect_name)
                
			# If there are no options but it's a yes/no field, use BooleanField
			elif 'Yes' in [v['localizedValue'] for v in aspect.get('aspectValues', [])] and 'No' in [v['localizedValue'] for v in aspect.get('aspectValues', [])]:
				serializer_fields[aspect_name] = serializers.BooleanField(required=False)
				item_specifics_name.append(aspect_name)
			else:
				# Otherwise, use CharField for free text fields
				serializer_fields[aspect_name] = serializers.CharField(
					required=False,
					allow_blank=True
				)
				item_specifics_name.append(aspect_name)
		
		# Dynamically create a Serializer class combining eBay specifics and model fields
		DynamicSerializer = type('DynamicItemSpecificsSerializer', (serializers.Serializer,), serializer_fields)
		return DynamicSerializer, item_specifics_name, valid_choices_field
	
	# Serializer for other marketplaces without item specifics
	def generate_other_marketplace_listing_fields_serializer():
		# Create a dictionary for dynamic serializer fields
		serializer_fields = {}
		model_class = []
		# Create a ModelSerializer class for the model fields
		class ModelSerializer(serializers.ModelSerializer):
			class Meta:
				model = InventoryModel
				exclude = [
					'id',
					'market_item_id',
					'user',

				]

		# Extract model fields (excluding the ones already present in eBay item specifics)
		for field_name, field_instance in ModelSerializer().get_fields().items():
			if field_name not in serializer_fields:
				serializer_fields[field_name] = field_instance
				model_class.append(field_name)

		# Dynamically create a Serializer class combining eBay specifics and model fields
		DynamicSerializer = type('DynamicItemSpecificsSerializer', (serializers.Serializer,), serializer_fields)
		return DynamicSerializer


	
class UploadedProductImageSerializer(serializers.ModelSerializer):

    class Meta:
        model = UploadedProductImage
        fields = ['image_url']


class WooComerceEnrolSerializer(serializers.ModelSerializer):
	marketplace_name = serializers.CharField(required=False, allow_blank=True)

	class Meta:
		model = MarketplaceEnronment
		exclude = ('_id', 'user', 'access_token', 'refresh_token', 'enable_charity', 'charity_id', 'donation_percentage', 'enable_best_offer', 'warn_copyright_complaints', 'warn_restriction_violation', 'shipping_policy', 'return_policy', 'payment_policy')

	def update(self, instance, validated_data):
		validated_data.pop('user_id', None)
		return super().update(instance, validated_data)