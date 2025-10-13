from django.core.management.base import BaseCommand
from accounts.models import Charge

class Command(BaseCommand):
    help = "Seeds the database with predefined charges"
    
    def handle(self, *args, **kwargs):
        charge_data = [
            {
                'key': 'custom_supplier',
                "label": "Custom Supplier Integration",
                "description": "Charge for priority integration of a user-requested supplier (force integration).",
                "base_amount": 190.00,
                "charge_fixed": 0.30,
                "charge_percent": 2.9,
            }
        ]
        for charge in charge_data:
            obj, created = Charge.objects.get_or_create(
                key=charge['key'],
                defaults={
                    'label': charge['label'],
                    'description': charge['description'],
                    'base_amount': charge['base_amount'],
                    'charge_fixed': charge['charge_fixed'], 
                    'charge_percent': charge['charge_percent'],
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created charge: {charge['key']}"))
            else:
                self.stdout.write(self.style.WARNING(f"Charge already exists: {charge['key']}"))
                
        self.stdout.write(self.style.SUCCESS("Charges seeding complete!"))
        