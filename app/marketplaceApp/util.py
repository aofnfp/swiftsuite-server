from inventoryApp.models import InventoryModel
from .models import MarketplaceEnronment
import logging
logger = logging.getLogger(__name__)

def complete_enrolment_price_update(userid, market_name):
    market_env = MarketplaceEnronment.objects.filter(user_id=userid, marketplace_name=market_name).first()
    all_items = InventoryModel.objects.filter(user_id=userid, market_name=market_name)
    for item in all_items:
        try:
            # Modify selling price before updating on marketplace
            if item.total_product_cost:
                selling_price = float(item.total_product_cost) + float(item.fixed_markup) + ((float(item.fixed_percentage_markup)/100) * float(item.total_product_cost)) + ((float(item.profit_margin)/100) * float(item.total_product_cost))
                # Bug 1 & 6: enforce MAP when wc_map_enforcement is enabled
                if market_env and market_name == "Woocommerce": 
                    if market_env.wc_map_enforcement and item.map:
                        try:
                            selling_price = max(selling_price, float(item.map))
                        except (TypeError, ValueError) as map_err:
                            logger.warning(f"MAP enforcement skipped for SKU {item.sku}: {map_err}")
                else:                    # Bug 2: enforce MAP when wc_map_enforcement is disabled
                    if item.map:
                        try:
                            selling_price = max(selling_price, float(item.map))
                        except (TypeError, ValueError) as map_err:
                            logger.warning(f"MAP enforcement skipped for SKU {item.sku}: {map_err}")
                inventory, created = InventoryModel.objects.update_or_create(id=item.id, defaults=dict(start_price=round(selling_price, 2)))
        except Exception as e:
            print(f"Failed to update items selling price for user: {userid} with sku: {item.sku}. Error: {e}")
            continue



