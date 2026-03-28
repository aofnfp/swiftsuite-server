from django.core.management.base import BaseCommand
from accounts.models import User, Module, SubAccountPermissions

class Command(BaseCommand):
    help = "Seed default permissions for all existing subaccounts"

    def handle(self, *args, **kwargs):
        modules = Module.objects.all()
        if not modules.exists():
            self.stdout.write(self.style.ERROR("❌ No modules found. Run `python manage.py seed_modules` first."))
            return

        subaccounts = User.objects.filter(parent__isnull=False)  # Only subaccounts
        if not subaccounts.exists():
            self.stdout.write(self.style.WARNING("⚠️ No subaccounts found."))
            return

        for subaccount in subaccounts:
            for module in modules:
                perm, created = SubAccountPermissions.objects.get_or_create(
                    user=subaccount,
                    module=module,
                    defaults={
                        "can_view": True,
                        "can_edit": False,
                        "can_delete": False,
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(
                        f"✅ Created permissions for {subaccount.email} on {module.name}"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"⚠️ Permissions already exist for {subaccount.email} on {module.name}"
                    ))

        self.stdout.write(self.style.SUCCESS("🎉 Permissions seeding complete!"))
