from inventoryApp.models import InventoryModel

def complete_enrolment_price_update(userid, market_name):    
    all_items = InventoryModel.objects.filter(user_id=userid, market_name=market_name)
    for item in all_items:
        try:        
            # Modify selling price before updating on ebay 
            if item.total_product_cost:
                selling_price = float(item.total_product_cost) + float(item.fixed_markup) + ((float(item.fixed_percentage_markup)/100) * float(item.total_product_cost)) + ((float(item.profit_margin)/100) * float(item.total_product_cost))
                inventory, created = InventoryModel.objects.update_or_create(id=item.id, defaults=dict(start_price=round(selling_price, 2)))
        except Exception as e:
            print(f"Failed to update items selling price: {e}")
            continue