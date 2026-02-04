from django.core.cache import cache
import requests
from marketplaceApp.models import MarketplaceEnronment
from celery import shared_task
from celery.exceptions import Ignore
from .utils import sync_ebay_order_with_local, create_vendor_order_log, manual_sync_order_with_local, background_refresh_access_token, push_tracking_to_ebay
from .models import OrdersOnEbayModel, VendorOrderLog
from django.db.models import Exists, OuterRef
from django.utils import timezone
from datetime import timedelta
import logging
logger = logging.getLogger(__name__)


LOCK_KEY = "sync_ebay_order_task_lock"
LOCK_TIMEOUT = 60 * 30  # 30 minutes adjust based on max runtime
@shared_task(queue='default')
def sync_ebay_order_task():
    # Attempt to acquire lock; skip if already running
    if not cache.add(LOCK_KEY, "1", timeout=LOCK_TIMEOUT):
        logger.info("sync_ebay_order_task skipped: already running")
        return "Skipped (already running)"

    logger.info("sync_ebay_order_task started")
    try:
        # Call your existing sync logic
        sync_ebay_order_with_local()
        logger.info("sync_ebay_order_task completed successfully")
        return "Completed successfully"
    finally:
        # Always release the lock
        cache.delete(LOCK_KEY)



LOCK_KEY1 = "manual_sync_order_with_local_lock"
LOCK_TIMEOUT = 60 * 30  # 30 minutes adjust based on max runtime
@shared_task(queue='default')
def manual_sync_order_with_local_task(userid):
    # Attempt to acquire lock; skip if already running
    if not cache.add(LOCK_KEY1, "1", timeout=LOCK_TIMEOUT):
        logger.info("manual_sync_order_with_local_task skipped: already running")
        return "Skipped (already running)"

    logger.info("manual_sync_order_with_local_task started")
    try:
        # Call your existing sync logic
        manual_sync_order_with_local(userid)
        logger.info("manual_sync_order_with_local_task completed successfully")
        return "Completed successfully"
    finally:
        # Always release the lock
        cache.delete(LOCK_KEY)


LOCK_KEY2 = "background_refresh_access_token_lock"
LOCK_TIMEOUT2 = 60 * 10  # 10 minutes adjust based on max runtime
@shared_task(queue='heavy-inv')
def background_refresh_access_token_task():
    # Attempt to acquire lock; skip if already running
    if not cache.add(LOCK_KEY2, "1", timeout=LOCK_TIMEOUT2):
        logger.info("background_refresh_access_token_task skipped: already running")
        return "Skipped (already running)"

    logger.info("background_refresh_access_token_task started")
    try:
        # Call your existing sync logic
        access_token = background_refresh_access_token()
        logger.info(f"background_refresh_access_token_task completed successfully with access token: {access_token}")
        return f"Refresh access token completed successfully with access token: {access_token}"
    finally:
        # Always release the lock
        cache.delete(LOCK_KEY2)


@shared_task(queue='heavy-cpu')
def process_vendor_orders():
    """Function to process vendor orders"""
    cutoff_date = timezone.now() - timedelta(days=2)
    ACTIVE_STATUSES = [
        VendorOrderLog.VendorOrderStatus.CREATED,
        VendorOrderLog.VendorOrderStatus.PROCESSING,
        VendorOrderLog.VendorOrderStatus.SHIPPED,
        VendorOrderLog.VendorOrderStatus.DELIVERED,
    ]

    active_vendor_orders = VendorOrderLog.objects.filter(
        order=OuterRef("pk"),
        status__in=ACTIVE_STATUSES,
    )

    orders = (
        OrdersOnEbayModel.objects
        .filter(
            creationDate__gte=cutoff_date,
            orderPaymentStatus="PAID",
            orderFulfillmentStatus="NOT_STARTED",
        )
        .annotate(has_active_vendor_order=Exists(active_vendor_orders))
        .filter(has_active_vendor_order=False)
    )
    
    for order in orders:
        order_log = create_vendor_order_log(order)
        
        # dispatch order to vendor
        if order_log:
            if not order_log.enrollment:
                continue
            dispatch_order.delay(order_log.id)
        else:
            logger.info(
                f"Skipped VendorOrderLog creation for order {order.orderId} "
                f"(already has active vendor order)"
            )
            
    logger.info("order log entries created for vendor orders and dispatched.")
        

@shared_task(queue='heavy-cpu')
def dispatch_order(vendor_order_log_id: int):
    """Function to dispatch order to vendor"""

    try:
        vendor_order_log = VendorOrderLog.objects.get(id=vendor_order_log_id)
        vendor_name = vendor_order_log.vendor.lower()
        
        logger.info(
            f"Dispatching VendorOrderLog={vendor_order_log_id} "
            f"to vendor={vendor_name}"
        )

        if vendor_name == 'fragrancex':
            from .fragranceX_order import FrgxOrderApiClient
            client = FrgxOrderApiClient(vendor_order_log)
            order_details = client.get_order_details()
            bulk_order = client.build_bulk_payload(order_details)
            result = client.place_bulk_order(bulk_order)
            if result.get("Message", False) and result.get("BulkOrderId", False):
                vendor_order_log.status = VendorOrderLog.VendorOrderStatus.PROCESSING
                vendor_order_log.vendor_order_id = result.get("BulkOrderId")
                vendor_order_log.raw_response = result
                vendor_order_log.save()
                
                logger.info(f"Order {vendor_order_log.id} placed successfully with Fragrancex.")
            else:
                vendor_order_log.status = VendorOrderLog.VendorOrderStatus.FAILED
                vendor_order_log.error_message = str(result)
                vendor_order_log.raw_response = result
                vendor_order_log.save()
                logger.error(f"Failed to place order {vendor_order_log.id} with Fragrancex. Error: {result}")

        elif vendor_name == 'rsr':
            from .rsr_order import RsrOrderApiClient
            client = RsrOrderApiClient(vendor_order_log)
            order_details = client.get_order_details()
            payload = client.build_payload(order_details)
            result = client.place_order(payload)
            if result.get("StatusCode") == "00":
                vendor_order_log.status = VendorOrderLog.VendorOrderStatus.PROCESSING
                vendor_order_log.vendor_order_id = (
                    result.get("ConfirmResp") or result.get("WebRef")
                )
                vendor_order_log.raw_response = result
                vendor_order_log.save()

                logger.info(f"Order {vendor_order_log.id} placed successfully with RSR.")
            else:
                vendor_order_log.status = VendorOrderLog.VendorOrderStatus.FAILED
                vendor_order_log.error_message = result.get("StatusMssg", "RSR order failed")
                vendor_order_log.raw_response = result
                vendor_order_log.save()

                logger.error(f"Failed to place order {vendor_order_log.id} with RSR. Error: {result.get('StatusMssg')}")
        
    except VendorOrderLog.DoesNotExist:
        logger.error(f"VendorOrderLog with id {vendor_order_log_id} does not exist.")


@shared_task(queue='heavy-cpu')
def check_vendor_order_status():
    """Background task to check status of processing vendor orders (RSR, FragranceX)"""
    logger.info("Starting check_vendor_order_status task")
    
    processing_orders = VendorOrderLog.objects.filter(
        status=VendorOrderLog.VendorOrderStatus.PROCESSING
    )

    count = 0
    updated_count = 0
    
    for vendor_order in processing_orders:
        count += 1
        vendor_name = vendor_order.vendor.lower()
        
        try:
            status_updated = False
            
            if vendor_name == 'rsr':
                from .rsr_order import RsrOrderApiClient
                client = RsrOrderApiClient(vendor_order)
                payload = client.build_check_order_payload(vendor_order)
                result = client.check_order(payload)
                
                if result.get("StatusCode") == "00":
                    if client.update_local_status(result):
                        status_updated = True

            elif vendor_name == 'fragrancex':
                from .fragranceX_order import FrgxOrderApiClient
                client = FrgxOrderApiClient(vendor_order)
                if client.check_and_update_status():
                    status_updated = True
            
            if status_updated:
                # push_tracking_to_ebay(vendor_order)
                updated_count += 1

        except Exception as e:
            logger.error(f"Error checking status for order {vendor_order.id} (Vendor: {vendor_name}): {e}")
            continue
            
    logger.info(f"Completed check_vendor_order_status. Checked {count} orders, updated {updated_count} successfully.")