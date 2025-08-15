from django.core.management.base import BaseCommand
from swiftsuite.vendorEnrollment.models import BackgroundTask
from swiftsuite.vendorEnrollment.views import update_vendor_data

class Command(BaseCommand):
    help = "Processes queued vendor update tasks"

    def handle(self, *args, **kwargs):
        tasks = BackgroundTask.objects.all()
        for task in tasks:
            try:
                enrollment = task.enrollment
                self.stdout.write(f"Processing enrollment {enrollment.identifier}")
                update_vendor_data(enrollment)
                task.processed = True
                task.result = "Success"
                
            except Exception as e:
                task.result = f"Error: {str(e)}"
                self.stderr.write(task.result)
                
            finally:
                task.save()
