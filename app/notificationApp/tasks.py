from celery import shared_task
from .dispatcher import dispatch_notifications  


@shared_task
def run_notification_dispatcher():
    """
    Celery task wrapper for dispatching notifications.
    This is what Celery Beat will schedule.
    """
    dispatch_notifications()
