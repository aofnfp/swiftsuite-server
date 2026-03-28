from django.core.management.base import BaseCommand
from accounts.models import Tier


class Command(BaseCommand):
    help = "Seeds the database with predefined tiers"
    
    def handle(self, *args, **kwargs):
        tiers_data = [
        {
            "name": "Starter",
            "description": "500 orders/month, 1 store, 5 vendors. Inventory sync, Email & Chat support.",
            "price": 249.00,
            "included_orders": 500,
            "extra_order_cost": 0.20,
            "included_stores": 1,
            "extra_store_cost": 50.00,
            "store_sku_limit": 250000,
            "extra_sku_cost": 10.00,
            "included_vendors": 5,
            "extra_vendor_cost": 20.00,
            "max_subaccounts": 1,  
            "inventory_sync": True,
            "api_access": False,
            "branded_tracking": False,
            "dedicated_success_manager": False,
            "white_label_branding": False,
            "advanced_analytics": False,
        },
        {
            "name": "Growth",
            "description": "2000 orders/month, 2 stores, 10 vendors. Advanced routing, Branded tracking, API access.",
            "price": 449.00,
            "included_orders": 2000,
            "extra_order_cost": 0.20,
            "included_stores": 2,
            "extra_store_cost": 50.00,
            "store_sku_limit": 250000,
            "extra_sku_cost": 10.00,
            "included_vendors": 10,
            "extra_vendor_cost": 20.00,
            "max_subaccounts": 3,
            "inventory_sync": True,
            "api_access": True,
            "branded_tracking": True,
            "dedicated_success_manager": False,
            "white_label_branding": False,
            "advanced_analytics": False,
        },
        {
            "name": "Premium",
            "description": "5000 orders/month, 3 stores, 20 vendors. Smart fulfillment, White-label branding, Dedicated success manager.",
            "price": 999.00,
            "included_orders": 5000,
            "extra_order_cost": 0.20,
            "included_stores": 3,
            "extra_store_cost": 50.00,
            "store_sku_limit": 250000,
            "extra_sku_cost": 10.00,
            "included_vendors": 20,
            "extra_vendor_cost": 20.00,
            "max_subaccounts": 5,
            "inventory_sync": True,
            "api_access": True,
            "branded_tracking": True,
            "dedicated_success_manager": True,
            "white_label_branding": True,
            "advanced_analytics": False,
        },
        {
            "name": "Enterprise",
            "description": "Unlimited orders, stores, vendors. SLA-backed uptime, Dedicated account manager, Custom supplier integrations.",
            "price": 0.00,  # Custom pricing
            "included_orders": 9999999,
            "extra_order_cost": 0.00,
            "included_stores": 9999999,
            "extra_store_cost": 0.00,
            "store_sku_limit": 9999999,
            "extra_sku_cost": 0.00,
            "included_vendors": 9999999,
            "extra_vendor_cost": 0.00,
            "max_subaccounts": 50,  # Arbitrary high number
            "inventory_sync": True,
            "api_access": True,
            "branded_tracking": True,
            "dedicated_success_manager": True,
            "white_label_branding": True,
            "advanced_analytics": True,
        },
        ]

        for tier_data in tiers_data:
            Tier.objects.update_or_create(
                name=tier_data["name"],
                defaults=tier_data
            )

        self.stdout.write(self.style.SUCCESS("Tiers seeded successfully!"))