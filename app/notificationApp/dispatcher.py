from accounts.models import User
from .models import NotificationTemplate, Notification
from django.utils import timezone
from .services import SENDER_REGISTRY
from .scheduler import should_send_template
from django.db.models import Q



def _resolve_recipients(recipient_list):
    """Return queryset of users based on the recipients field."""
    
    qs = User.objects.filter(is_active=True)

    if "all_users" in recipient_list:
        return qs

    filters = Q()

    if "team_admins" in recipient_list:
        filters |= Q(parent__isnull=True)

    if "subaccounts" in recipient_list:
        filters |= Q(parent__isnull=False)

    if filters:
        return qs.filter(filters).distinct()

    return User.objects.none()


def dispatch_notifications():
    """Loops through all notification templates and sends notifications."""

    templates = NotificationTemplate.objects.all()

    for template in templates:
        
        if not should_send_template(template):
            continue
        
        recipients = _resolve_recipients(template.recipients)

        for user in recipients:
            for notif_type in template.types:

                sender_class = SENDER_REGISTRY.get(notif_type)
                if not sender_class:
                    continue

                # Create the Notification log row (pending status)
                notification_log = Notification.objects.create(
                    template=template,
                    recipient_user=user,
                    channel=notif_type,
                    status=Notification.Status.PENDING,
                )

                try:
                    # Initialize and send via the appropriate sender class
                    sender = sender_class(notification_log)
                    sender.send()

                    notification_log.status = Notification.Status.SENT
                    notification_log.sent_at = timezone.now()

                except Exception as e:
                    notification_log.status = Notification.Status.FAILED
                    notification_log.error_message = str(e)

                notification_log.save()
                
        template.last_sent_at = timezone.now()
        template.save()