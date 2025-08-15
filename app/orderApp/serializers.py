from rest_framework import serializers
from .models import CancelOrderModel



class CancelOrderModelSerializer(serializers.ModelSerializer):
	class Meta:
		model = CancelOrderModel
		fields = [
			"cancel_reason",
		]