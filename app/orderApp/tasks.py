from celery import shared_task
from .utils import sync_ebay_order_with_local
from .models import OrdersOnEbayModel, VendorOrderLog
from vendorEnrollment.models import Enrollment
import logging
logger = logging.getLogger(__name__)


@shared_task(queue='default')
def sync_ebay_order_task():
    """Background task to sync eBay items with local database"""
    sync_ebay_order_with_local()
    return "Order Sync completed successfully"


def create_vendor_order_log(order: OrdersOnEbayModel):
    from inventoryApp.models import InventoryModel
    
    if VendorOrderLog.objects.filter(
        order=order,
        vendor=order.vendor_name,
    ).exclude(status=VendorOrderLog.VendorOrderStatus.FAILED).exists():
        return

    # get item on inventory using the marketItemId
    product = InventoryModel.objects.filter(
        market_item_id=order.marketItemId
    ).first()
    if not product:
        logger.error(f"Product with marketItemId {order.marketItemId} not found in inventory.")
        return
    
    enrollment = Enrollment.objects.get(id=product.product.enrollment.id)
    if not enrollment:
        logger.error(f"Enrollment not found for product with marketItemId {order.marketItemId}.")
        return
    
    order_log = VendorOrderLog.objects.create(
        order=order,
        enrollment=enrollment,
        vendor=order.vendor_name,
        status=VendorOrderLog.VendorOrderStatus.CREATED,
    )
    
    return order_log    


@shared_task(queue='default')
def process_vendor_orders():
    """Function to process vendor orders"""
    all_orders = OrdersOnEbayModel.objects.filter(orderPaymentStatus='PAID', orderFulfillmentStatus='NOT_STARTED')
    
    for order in all_orders:
        order_log = create_vendor_order_log(order)
        
        # dispatch order to vendor
        if order_log:
            dispatch_order.delay(order_log)
        
    logger.info("order log entries created for vendor orders and dispatched.")
        

@shared_task(queue='default')
def dispatch_order(vendor_order_log):
    """Function to dispatch order to vendor"""
    try:
        vendor_name = vendor_order_log.vendor.lower()
        if vendor_name == 'fragrancex':
            from .fragranceX_order import FrgxOrderApiClient
            client = FrgxOrderApiClient()
            order_details = client.get_order_details(vendor_order_log)
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
            pass


        logger.info(f"Dispatching order {vendor_order_log.id} to vendor {vendor_order_log.vendor}.")
        
    except VendorOrderLog.DoesNotExist:
        logger.error(f"VendorOrderLog with id {vendor_order_log.id} does not exist.")