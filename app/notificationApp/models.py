from django.db import models

# Create your models here.

class NotificationTemplate(models.Model):
    class TriggerType(models.TextChoices):
        IMMEDIATELY = "immediately", "Immediately"
        RECURRING = "recurring", "Recurring"
        CUSTOM = "custom", "Custom"

    class Type(models.TextChoices):
        EMAIL = "email", "Email"
        IN_APP = "in_app", "In-App"
        PUSH = "push", "Push Notification"

    class Recipient(models.TextChoices):
        ALL_USERS = "all_users", "All Users"
        TEAM_ADMINS = "team_admins", "Team Admins"
        SUBACCOUNTS = "subaccounts", "Subaccounts"
        
    class RecurringFrequency(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        HOURLY = "hourly", "Hourly"
        INTERVAL_DAYS = "interval_days", "Every X Days"
        INTERVAL_HOURS = "interval_hours", "Every X Hours"

    types = models.JSONField()  
    recipients = models.JSONField()  

    category = models.CharField(max_length=100)
    header = models.CharField(max_length=255)
    body = models.TextField() 

    trigger_type = models.CharField(max_length=20, choices=TriggerType.choices)
    date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    
    recurring_frequency = models.CharField(max_length=20, choices=RecurringFrequency.choices, null=True, blank=True)
    recurring_interval = models.PositiveIntegerField(null=True, blank=True, help_text="Used when frequency is interval_days or interval_hours")
    recurring_start = models.DateTimeField(null=True, blank=True)
    recurring_end = models.DateTimeField(null=True, blank=True)

    last_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.category} - {self.header}"
    
    

class Notification(models.Model):
    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        PENDING = "pending", "Pending"  
    
    
    # TEMPLATE NOTIFICATION (optional)
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.CASCADE,
        related_name="logs",
        null=True, 
        blank=True
    )

    # EVENT-BASED NOTIFICATION (optional)
    title = models.CharField(max_length=255, null=True, blank=True)
    message = models.TextField(null=True, blank=True)
    data = models.JSONField(null=True, blank=True)
    
    recipient_user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name="notifications")
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, choices=Status.choices)  # e.g., "sent", "failed"
    read = models.BooleanField(default=False)
    error_message = models.TextField(null=True, blank=True)
    channel = models.CharField(max_length=20, default="in_app")  # e.g., "email", "push", "in_app"

    def __str__(self):
        return f"Notification to {self.recipient_user.email} at {self.sent_at} - {self.status}"
    
