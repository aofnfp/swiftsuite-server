from django.utils import timezone
from datetime import timedelta
from .models import NotificationTemplate
import datetime

def should_send_template(template: NotificationTemplate) -> bool:
    now = timezone.now()

    # -------------------------
    # 1. IMMEDIATELY (send once)
    # -------------------------
    if template.trigger_type == NotificationTemplate.TriggerType.IMMEDIATELY:
        return template.last_sent_at is None

    # -------------------------
    # 2. CUSTOM (send once on date + time)
    # -------------------------
    if template.trigger_type == NotificationTemplate.TriggerType.CUSTOM:
        if template.last_sent_at:
            return False

        if template.date and template.time:
            scheduled_dt = timezone.make_aware(
                datetime.datetime.combine(template.date, template.time)
            )
            return now >= scheduled_dt

        return False

    # -------------------------
    # 3. RECURRING (send based on frequency)
    # -------------------------
    if template.trigger_type == NotificationTemplate.TriggerType.RECURRING:

        # If not started yet
        if template.recurring_start and now < template.recurring_start:
            return False

        # If ended
        if template.recurring_end and now > template.recurring_end:
            return False
        
        last = template.last_sent_at or template.recurring_start or now

        freq = template.recurring_frequency

        if freq == NotificationTemplate.RecurringFrequency.DAILY:
            return now - last >= timedelta(days=1)

        if freq == NotificationTemplate.RecurringFrequency.WEEKLY:
            return now - last >= timedelta(weeks=1)

        if freq == NotificationTemplate.RecurringFrequency.MONTHLY:
            return now.month != last.month or now.year != last.year
        
        if freq == NotificationTemplate.RecurringFrequency.HOURLY:
            return now - last >= timedelta(hours=1)

        if freq == NotificationTemplate.RecurringFrequency.INTERVAL_DAYS:
            return now - last >= timedelta(days=template.recurring_interval)

        if freq == NotificationTemplate.RecurringFrequency.INTERVAL_HOURS:
            return now - last >= timedelta(hours=template.recurring_interval)

    return False
