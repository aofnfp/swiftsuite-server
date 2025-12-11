from celery import shared_task
from .util import complete_enrolment_price_update


@shared_task(queue='default')
def complete_enrolment_price_update_task(userid, market_name):
    """Background task to check if eBay items have ended"""
    complete_enrolment_price_update(userid, market_name)
    return "Check eBay item ended completed successfully"