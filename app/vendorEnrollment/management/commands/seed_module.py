from django.core.management.base import BaseCommand
from accounts.models import Module

class Command(BaseCommand):
    help = "Seed default modules into the database"

    DEFAULT_MODULES = [
        "Inventory",
        "Orders",
        "Customer Care",
        "Accounts",
    ]

    def handle(self, *args, **kwargs):
        for module_name in self.DEFAULT_MODULES:
            module, created = Module.objects.get_or_create(name=module_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created module: {module_name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Module already exists: {module_name}"))

        self.stdout.write(self.style.SUCCESS("Modules seeding complete!"))
