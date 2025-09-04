from .utils import VendorActivity
from .models import Vendors
from django.core.cache import cache
import logging
from celery import shared_task
from .utils import get_suppliers_for_vendor

logger = logging.getLogger(__name__)

@shared_task
def process_vendor_data(supplier, task_id, vendor_id):
    try:
        vendor_info = Vendors.objects.get(id=vendor_id)
        logger.info(f"Processing vendor data for {vendor_info.name}")
        pull = VendorActivity()
        result = pull.main(supplier)
        
        cache.set(f"upload_progress_{task_id}", 10)
        
        if result:
            logger.info(f"Vendor data processed successfully for {vendor_info.name}")
            vendor_info.has_data = True
            vendor_info.save()
            cache.set(f"upload_progress_{task_id}", 100)
        else:
            cache.set(f"upload_progress_{task_id}", -1)
            
    except Exception as e:
        # Log the exception for debugging
        logger.exception("Error processing vendor data")
        cache.set(f"upload_progress_{task_id}", -1)

    finally:
        # Clean up resources, if any
        pull.removeFile()
        cache.delete(f"upload_progress_{task_id}")

@shared_task
def reload_all_vendors():
    vendors = Vendors.objects.all()
    pull = VendorActivity()
    
    for vendor in vendors:
    
        if vendor.name == "fragrancex":
            supplier =  (vendor.name, vendor.api_access_id, vendor.api_access_key)
        elif vendor.name == "rsr":
            supplier = (vendor.name, vendor.username, vendor.password, vendor.pos)
        else:
            supplier = get_suppliers_for_vendor(vendor.name, vendor.host, vendor.ftp_username, vendor.ftp_password)
        
        pull.main(supplier)
        