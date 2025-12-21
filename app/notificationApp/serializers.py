from rest_framework import serializers
from .models import NotificationTemplate, Notification


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = "__all__"
        
    def validate_types(self, value):
        valid_types = {choice[0] for choice in NotificationTemplate.Type.choices}
        if not all(t in valid_types for t in value):
            raise serializers.ValidationError("Invalid notification type in types field.")
        return value
    
    def validate_recipients(self, value):
        valid_recipients = {choice[0] for choice in NotificationTemplate.Recipient.choices}
        if not all(r in valid_recipients for r in value):
            raise serializers.ValidationError("Invalid recipient type in recipients field.")
        return value
    
    def validate(self, data):
        trigger_type = data.get("trigger_type")
        date = data.get("date")
        time = data.get("time")
        frequency = data.get("recurring_frequency")
        interval = data.get("recurring_interval")
        
        if trigger_type == NotificationTemplate.TriggerType.CUSTOM:
            if date is None or time is None:
                raise serializers.ValidationError("Both date and time must be provided for custom trigger type.")
            
        if trigger_type in {NotificationTemplate.TriggerType.IMMEDIATELY, NotificationTemplate.TriggerType.RECURRING}:
            if date is not None or time is not None:
                raise serializers.ValidationError("Date and time must be null for immediately or recurring trigger types.")
            
        # RECURRING VALIDATION
        if trigger_type == NotificationTemplate.TriggerType.RECURRING:
            if not frequency:
                raise serializers.ValidationError("Recurring frequency is required.")

            if frequency in {"interval_days", "interval_hours"} and not interval:
                raise serializers.ValidationError(
                    "Interval value is required when frequency is interval_days or interval_hours."
                )
                
        return data
    
class NotificationSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "data",
            "status",
            "read",
            "sent_at",
            "error_message",
        ]
        
    def get_title(self, obj):
        if obj.template:
            return obj.template.header
        return obj.title
    
    def get_message(self, obj):
        if obj.template:
            return obj.template.body
        return obj.message