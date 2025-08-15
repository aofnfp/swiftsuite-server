from django.utils.deprecation import MiddlewareMixin
import threading

from .models import VendoEnronment
from .update import periodic_task

class StartupMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response
        self.has_run = False  # Ensure it only runs once
        super().__init__(get_response)
        

    def __call__(self, request):
        if not self.has_run:
            print("Fetch all enrolled vendors")
            self.has_run = True
            self.run_pull_update_on_startup()
        return self.get_response(request)

    def run_pull_update_on_startup(self):
        # Fetch all enrolled vendors
        
        enrolled_vendors = VendoEnronment.objects.all().exclude(vendor_name = "FragranceX")
        for vendor in enrolled_vendors:
            thread = threading.Thread(
                target=periodic_task,
                args=(
                    vendor.vendor_name,
                    vendor.user_id,
                    vendor.host,
                    vendor.ftp_username,
                    vendor.ftp_password,
                    vendor.apiAccessId,
                    vendor.apiAccessKey,
                    vendor.Username,
                    vendor.Password,
                    vendor.POS
                ),
                daemon=True
            )
            thread.start()