from django.core.cache import cache
from celery import shared_task
from celery.exceptions import Ignore
from .utils import sync_ebay_order_with_local
from .models import OrdersOnEbayModel, VendorOrderLog
from .utils import create_vendor_order_log
import logging
logger = logging.getLogger(__name__)


LOCK_KEY = "sync_ebay_order_task_lock"
LOCK_TIMEOUT = 7200  # 2 hours, adjust based on max runtime
@shared_task(bind=True, queue='default')
def sync_ebay_order_task(self):
    # Attempt to acquire lock; skip if already running
    if not cache.add(LOCK_KEY, "1", timeout=LOCK_TIMEOUT):
        logger.info("sync_ebay_order_task skipped: already running")
        raise Ignore()  # Skipped task is ignored in Celery

    logger.info("sync_ebay_order_task started")
    try:
        # Call your existing sync logic
        sync_ebay_order_with_local()
        logger.info("sync_ebay_order_task completed successfully")
    finally:
        # Always release the lock
        cache.delete(LOCK_KEY)


@shared_task(queue='default')
def process_vendor_orders():
    """Function to process vendor orders"""
    all_orders = OrdersOnEbayModel.objects.filter(orderPaymentStatus='PAID', orderFulfillmentStatus='NOT_STARTED').exclude(
        vendororderlog__status__in=[
            VendorOrderLog.VendorOrderStatus.CREATED,
            VendorOrderLog.VendorOrderStatus.PROCESSING,
            VendorOrderLog.VendorOrderStatus.SHIPPED
        ]
    )
    
    for order in all_orders:
        order_log = create_vendor_order_log(order)
        
        # dispatch order to vendor
        if order_log:
            dispatch_order.delay(order_log.id)
        
    logger.info("order log entries created for vendor orders and dispatched.")
        

@shared_task(queue='default')
def dispatch_order(vendor_order_log_id: int):
    """Function to dispatch order to vendor"""
    try:
        vendor_order_log = VendorOrderLog.objects.get(id=vendor_order_log_id)
        vendor_name = vendor_order_log.vendor.lower()
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
            if result.get("StatusCode") == 0:
                vendor_order_log.status = VendorOrderLog.VendorOrderStatus.PROCESSING
                vendor_order_log.vendor_order_id = result.get("OrderNum") or vendor_order_log.reference_id
                vendor_order_log.raw_response = result
                vendor_order_log.save()

                logger.info(f"Order {vendor_order_log.id} placed successfully with RSR.")
            else:
                vendor_order_log.status = VendorOrderLog.VendorOrderStatus.FAILED
                vendor_order_log.error_message = result.get("StatusMssg")
                vendor_order_log.raw_response = result
                vendor_order_log.save()

                logger.error(f"Failed to place order {vendor_order_log.id} with RSR. Error: {result.get('StatusMssg')}")


        logger.info(f"Dispatching order {vendor_order_log.id} to vendor {vendor_order_log.vendor}.")
        
    except VendorOrderLog.DoesNotExist:
        logger.error(f"VendorOrderLog with id {vendor_order_log.id} does not exist.")