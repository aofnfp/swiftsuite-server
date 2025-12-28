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
    if VendorOrderLog.objects.filter(
        order=order,
        vendor=order.vendor_name,
    ).exclude(status=VendorOrderLog.VendorOrderStatus.FAILED).exists():
        return

    order_created = VendorOrderLog.objects.create(
        order=order,
        enrollment=Enrollment.objects.get(
            user=order.user,
            vendor__name__iexact=order.vendor_name
        ),
        vendor=order.vendor_name,
        status=VendorOrderLog.VendorOrderStatus.CREATED,
    )
    
    return order_created.id
    


@shared_task(queue='default')
def process_vendor_orders():
    """Function to process vendor orders"""
    all_orders = OrdersOnEbayModel.objects.filter(orderPaymentStatus='PAID', orderFulfillmentStatus='NOT_STARTED')
    
    for order in all_orders:
        log_id = create_vendor_order_log(order)
        
        # dispatch order to vendor
        if log_id:
            dispatch_order.delay(log_id)
        
    logger.info("order log entries created for vendor orders.")
        

@shared_task(queue='default')
def dispatch_order(vendor_order_log_id: int):
    """Function to dispatch order to vendor"""
    try:
        vendor_order_log = VendorOrderLog.objects.get(id=vendor_order_log_id)
        vendor_name = vendor_order_log.vendor.lower()
        if vendor_name == 'fragrancex':
            pass

        elif vendor_name == 'rsr':
            pass


        logger.info(f"Dispatching order {vendor_order_log.id} to vendor {vendor_order_log.vendor}.")
        
    except VendorOrderLog.DoesNotExist:
        logger.error(f"VendorOrderLog with id {vendor_order_log_id} does not exist.")