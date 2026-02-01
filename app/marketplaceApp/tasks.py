from celery import shared_task
from django.core.cache import cache
import logging
logger = logging.getLogger(__name__)
from celery.exceptions import Ignore
from .util import complete_enrolment_price_update#, background_access_token_refresh


@shared_task(queue='default')
def complete_enrolment_price_update_task(userid, market_name):
    """Background task to check if eBay items have ended"""
    complete_enrolment_price_update(userid, market_name)
    return "Complete enrolment price update task finished successfully."


# LOCK_TIMEOUT = 60 * 10
# LOCK_KEY = "refresh_access_token_task_lock"
# @shared_task(queue='heavy-inv')
# def refresh_access_token_task():
#     if not cache.add(LOCK_KEY, "1", timeout=LOCK_TIMEOUT):
#         logger.info("refresh_access_token_task skipped: already running")
#         return "Skipped (already running)"

#     logger.info("refresh_access_token_task started")

#     try:
#         background_access_token_refresh()
#         logger.info("refresh_access_token_task completed successfully")
#         return "access token refresh completed successfully"
#     finally:
#         cache.delete(LOCK_KEY)