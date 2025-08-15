from .models import VendoEnronment
from .views import VendorActivity, get_suppliers_for_vendor
import threading
from django.utils.deprecation import MiddlewareMixin
import asyncio
from asgiref.sync import sync_to_async


async def update_catalogue():
    # Fetch all VendoEnronment objects asynchronously
    vendoEnronments = await sync_to_async(list)(
        VendoEnronment.objects.all().exclude(vendor_name="Rsr")
    )

    # Create a list of async tasks
    tasks = []
    for vendoEnronment in vendoEnronments:
        # Fetch attributes asynchronously
        ftp_name = await sync_to_async(lambda: vendoEnronment.vendor_name)()
        userid = await sync_to_async(lambda: vendoEnronment.user.id)()

        # Initialize VendorActivity
        pull = VendorActivity()
        pull.update_catalog = True

        # Prepare supplier details
        if ftp_name == "Fragrancex":
            apiAccessId = await sync_to_async(lambda: vendoEnronment.apiAccessId)()
            apiAccessKey = await sync_to_async(lambda: vendoEnronment.apiAccessKey)()
            supplier = (ftp_name, apiAccessId, apiAccessKey)

        elif ftp_name == "RSR":
            Username = await sync_to_async(lambda: vendoEnronment.Username)()
            Password = await sync_to_async(lambda: vendoEnronment.Password)()
            POS = await sync_to_async(lambda: vendoEnronment.POS)()
            supplier = (ftp_name, Username, Password, POS)

        else:
            ftp_host = await sync_to_async(lambda: vendoEnronment.host)()
            ftp_user = await sync_to_async(lambda: vendoEnronment.ftp_username)()
            ftp_password = await sync_to_async(lambda: vendoEnronment.ftp_password)()
            supplier = await sync_to_async(get_suppliers_for_vendor)(
                ftp_name, ftp_host, ftp_user, ftp_password
            )
        
        # Add the async task to the list
        tasks.append(run_update_task(pull, supplier, userid))

    # Run all tasks concurrently
    await asyncio.gather(*tasks)
    print("All catalogs updated successfully.")


async def run_update_task(pull, supplier, userid):
    """
    Runs the catalog update task asynchronously.
    """
    try:
        # Run pull.main in a separate thread to avoid blocking
        await asyncio.to_thread(pull.main, supplier, userid)
        print(f"Catalog updated")
    except Exception as e:
        print(f"Error updating catalog: {e}")


async def run_catalog_update():
    """
    Periodic task that updates the catalog every 2 hours asynchronously.
    """
    while True:
        try:
            await update_catalogue()
        except Exception as e:
            print(f"Error updating catalog: {str(e)}")
        await asyncio.sleep(7200)  # Wait for 2 hours before running again


class StartupMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response
        self.has_run = False  # Ensure it only runs once
        super().__init__(get_response)

    def __call__(self, request):
        if not self.has_run:
            print("Fetch all enrolled vendors")
            self.has_run = True
            self.start_periodic_update()
        return self.get_response(request)

    def start_periodic_update(self):
        """
        Starts a periodic background thread to update the catalog every 2 hours.
        """
        thread = threading.Thread(target=self.run_async_loop, daemon=True)
        thread.start()

    def run_async_loop(self):
        """
        Runs the asynchronous event loop to start the periodic catalog update.
        """
        asyncio.run(run_catalog_update())
