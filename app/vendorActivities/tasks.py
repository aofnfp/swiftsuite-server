from .utils import VendorActivity
from .models import Vendors
from django.core.cache import cache
import logging

def process_rsr_in_background(payload, task_id, vendor_id):
    try:
        username = payload.get('username')
        password = payload.get('password')
        pos = payload.get('pos')
        supplier = ('rsr', username, password, pos)
        
        pull = VendorActivity()
        result = pull.main(supplier)
        
        cache.set(f"upload_progress_{task_id}", 10)
        
        if result:
            vendor_info = Vendors.objects.get(id=vendor_id)
            vendor_info.has_data = True
            vendor_info.save()
            pull.removeFile()
            cache.set(f"upload_progress_{task_id}", 100)
        else:
            cache.set(f"upload_progress_{task_id}", -1)
    except Exception as e:
        # Log the exception for debugging
        logging.error(f"Error processing RSR data: {e}")
        cache.set(f"upload_progress_{task_id}", -1)
        
