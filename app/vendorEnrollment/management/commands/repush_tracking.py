from django.core.management.base import BaseCommand
from orderApp.models import VendorOrderLog
from orderApp.utils import push_tracking_to_ebay


AFFECTED_ORDER_IDS = [
    "24-14249-44919",
    "27-14229-77031",
    "27-14227-99256",
    "12-14249-15621",
    "26-14228-95579",
    "03-14261-50386",
    "07-14255-86895",
    "18-14239-98760",
    "05-14258-98927",
    "13-14247-17403",
    "19-14238-35904",
    "22-14233-94015",
    "26-14228-16235",
    "10-14250-86429",
    "24-14245-59017",
    "06-14256-74412",
    "18-14239-39249",
    "21-14234-39457",
    "08-14252-26477",
    "12-14246-86728",
    "25-14228-08190",
    "05-14256-99277",
    "20-14235-04956",
    "14-14243-57390",
    "21-14232-90353",
    "25-14226-95910",
    "15-14240-82015",
    "07-14252-37481",
    "24-14242-56378",
    "03-14257-67492",
    "15-14240-43418",
    "11-14246-09634",
    "24-14242-19557",
    "15-14239-88775",
    "14-14241-32252",
    "16-14238-17288",
    "11-14245-00694",
    "01-14259-73088",
    "23-14227-73705",
    "24-14240-91664",
    "01-14259-16522",
    "23-14227-22748",
    "16-14236-97238",
    "11-14243-91967",
    "10-14244-54659",
    "24-14210-38819",
]


class Command(BaseCommand):
    help = "Re-push eBay tracking for FragranceX orders that have ghost fulfillments"

    def handle(self, *args, **kwargs):
        succeeded = []
        failed = []
        skipped = []

        for order_id in AFFECTED_ORDER_IDS:
            vendor_order = VendorOrderLog.objects.filter(
                order__orderId=order_id
            ).first()

            if not vendor_order:
                self.stdout.write(self.style.WARNING(f"[SKIP]  {order_id} — VendorOrderLog not found"))
                skipped.append(order_id)
                continue

            if not vendor_order.tracking_number or not vendor_order.carrier or not vendor_order.shipped_at:
                self.stdout.write(self.style.WARNING(f"[SKIP]  {order_id} — missing tracking info (number/carrier/date)"))
                skipped.append(order_id)
                continue

            # Reset ghost fulfillment state so push_tracking_to_ebay re-creates it
            vendor_order.status = VendorOrderLog.VendorOrderStatus.SHIPPED
            vendor_order.fulfillment_url = None
            vendor_order.delivered_at = None
            vendor_order.save(update_fields=["status", "fulfillment_url", "delivered_at"])

            result = push_tracking_to_ebay(vendor_order)

            if result and result.get("success"):
                self.stdout.write(self.style.SUCCESS(f"[OK]    {order_id} — tracking pushed and verified"))
                succeeded.append(order_id)
            else:
                status_code = result.get("status_code") if result else "N/A"
                raw_body = result.get("raw_body") if result else "N/A"
                self.stdout.write(self.style.ERROR(f"[FAIL]  {order_id} — status={status_code} body={raw_body}"))
                failed.append(order_id)

        self.stdout.write("\n--- Summary ---")
        self.stdout.write(self.style.SUCCESS(f"Succeeded : {len(succeeded)}"))
        self.stdout.write(self.style.ERROR(f"Failed    : {len(failed)}"))
        self.stdout.write(self.style.WARNING(f"Skipped   : {len(skipped)}"))

        if failed:
            self.stdout.write(self.style.ERROR("\nFailed orders:"))
            for oid in failed:
                self.stdout.write(f"  {oid}")
