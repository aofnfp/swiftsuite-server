from celery import shared_task
from django.core.cache import cache
import logging
logger = logging.getLogger(__name__)
from celery.exceptions import Ignore
from .util import complete_enrolment_price_update
from .views import Ebay
from .models import MarketplaceEnronment


@shared_task(queue='default')
def complete_enrolment_price_update_task(userid, market_name):
    """Background task to check if eBay items have ended"""
    complete_enrolment_price_update(userid, market_name)
    return "Complete enrolment price update task finished successfully."


LOCK_TIMEOUT = 60 * 10
LOCK_KEY = "refresh_access_token_task_lock"
@shared_task(queue='heavy-inv')
def background_refresh_access_token_task():
    if not cache.add(LOCK_KEY, "1", timeout=LOCK_TIMEOUT):
        logger.info("refresh_access_token_task skipped: already running")
        return "Skipped (already running)"

    logger.info("refresh_access_token_task started")

    user_data = MarketplaceEnronment.objects.filter(marketplace_name="Ebay")
    for user in user_data:
        try:
            eb = Ebay()
            access_token = eb.refresh_access_token(user.user_id, "Ebay")
            logger.info(f"refresh_access_token_task completed successfully for user {user.user_id} with access_token: {access_token}")
            return "access token refresh completed successfully"
        except Exception as e:
            logger.info(f"Failed to refresh access token for user {user.user_id} with error: {e}")
            continue
        finally:
            cache.delete(LOCK_KEY)
