from rest_framework import serializers


class ItemSerializer(serializers.Serializer):
    PartNum = serializers.CharField(max_length=100, required=False)
    WishQTY = serializers.IntegerField(required=False)


class PlaceOrderSerializer(serializers.Serializer):
    Username = serializers.CharField(max_length=255, required=False)
    Password = serializers.CharField(max_length=255, write_only=True, required=False)  # write_only to prevent returning sensitive data
    POS = serializers.CharField(max_length=100, required=False)
    PONum = serializers.CharField(max_length=100, required=False)
    ShipAddress = serializers.CharField(max_length=255, required=False)
    ShipCity = serializers.CharField(max_length=100, required=False)
    ShipState = serializers.CharField(max_length=100, required=False)
    ShipZip = serializers.CharField(max_length=20, required=False)
    ShipAcccount = serializers.CharField(max_length=255, required=False)
    ContactNum = serializers.CharField(max_length=20, required=False)
    Email = serializers.EmailField(required=False)
    Items = ItemSerializer(many=True, required=False)
    FillOrKill = serializers.IntegerField(min_value=0, max_value=1, required=False)
