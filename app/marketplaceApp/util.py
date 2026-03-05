from inventoryApp.models import InventoryModel, MarketPlaceUpdateLog
from .models import MarketplaceEnronment
import logging
logger = logging.getLogger(__name__)
import time, json, requests
from ratelimit import limits, sleep_and_retry
from django.utils import timezone
from inventoryApp.update_market import update_woocommerce_product_from_background


# Create a function to update items quantity and price at the background on Ebay
# Limit to 5 calls per second (eBay's typical limit)
@sleep_and_retry
@limits(calls=5, period=1)
def complete_enrollment_quantity_price_update_on_ebay(user_id, item_id, price, quantity, enroll_id):
    try:
        user_data = MarketplaceEnronment.objects.get(_id=enroll_id, marketplace_name="Ebay")
    except Exception as e:
        print(f"Failed to fetch access token")
        return None

    access_token =  user_data.access_token

    # eBay Trading API endpoint
    url = 'https://api.ebay.com/ws/api.dll'

    headers = {
        'X-EBAY-API-CALL-NAME': 'ReviseItem',
        'X-EBAY-API-SITEID': '0',  # Change this to your site ID, 0 is for US
        'X-EBAY-API-COMPATIBILITY-LEVEL': '1081',  # eBay API version
        'Content-Type': 'text/xml',
        'Authorization': f'Bearer {access_token}'
    }
   
    try:
        # XML Body for ReviseItem request
        body = f"""
            <?xml version="1.0" encoding="utf-8"?>
            <ReviseItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
                <RequesterCredentials>
                    <eBayAuthToken>{access_token}</eBayAuthToken>
                </RequesterCredentials>
                <Item>
                    <ItemID>{item_id}</ItemID>
                    <StartPrice>{str(price)}</StartPrice>
                    <Quantity>{str(quantity)}</Quantity>
                    <SellerProfiles>
                        <SellerPaymentProfile>
                            <PaymentProfileID>{json.loads(user_data.payment_policy).get('id')}</PaymentProfileID>
                        </SellerPaymentProfile>
                        <SellerReturnProfile>
                            <ReturnProfileID>{json.loads(user_data.return_policy).get('id')}</ReturnProfileID>
                        </SellerReturnProfile>
                        <SellerShippingProfile>
                            <ShippingProfileID>{json.loads(user_data.shipping_policy).get('id')}</ShippingProfileID>
                        </SellerShippingProfile>
                    </SellerProfiles>
                </Item>
            </ReviseItemRequest>
            """
        
        # Make the POST request
        response = requests.post(url, headers=headers, data=body)
        if response.status_code == 429:  # Rate limit hit
            retry_after = int(response.headers.get('Retry-After', 2))
            time.sleep(retry_after)
            return complete_enrollment_quantity_price_update_on_ebay(user_id, item_id, price, quantity, enroll_id)
        # Check the response
        if response.status_code == 200:
            return f"Success:{response.text}"
        else:
            return f"Error:{response.text}"
    except ConnectionError as e:
        return f'Error: {e}'


def complete_enrolment_price_update(userid, market_name):
    market_enrolled = MarketplaceEnronment.objects.filter(user_id=userid, marketplace_name=market_name).first()
    all_items = InventoryModel.objects.filter(user_id=userid, market_name=market_name)
    for item in all_items:
        try:
            # Modify selling price before updating on marketplace
            if item.total_product_cost and market_enrolled:
                selling_price = float(item.total_product_cost) + float(item.fixed_markup) + ((float(item.fixed_percentage_markup)/100) * float(item.total_product_cost)) + ((float(item.profit_margin)/100) * float(item.total_product_cost))
                # Enforce MAP when wc_map_enforcement is enabled
                if market_name == "Woocommerce": 
                    if market_enrolled.wc_map_enforcement and item.map:
                        try:
                            selling_price = max(round(selling_price, 2), float(item.map))
                        except (TypeError, ValueError) as map_err:
                            logger.warning(f"MAP enforcement skipped for SKU {item.sku}: {map_err}")
                    # Update the price and quantity of product on Woocommerce
                    response = update_woocommerce_product_from_background(item.market_item_id, selling_price, market_enrolled.maximum_quantity, userid)
                    if response == "Success":
                        item_to_save, created = MarketPlaceUpdateLog.objects.update_or_create(user_id=userid, inventory_id=item.id, defaults=dict(market_name="Woocommerce", vendor_name=item.vendor_name, updated_sku=item.sku, log_description=f"Updated price to {selling_price} and quantity to {market_enrolled.maximum_quantity} from vendor {item.vendor_name}"))
                elif market_name == "Ebay": 
                    if item.map:
                        try:
                            selling_price = max(round(selling_price, 2), float(item.map))
                        except (TypeError, ValueError) as map_err:
                            logger.warning(f"MAP enforcement skipped for SKU {item.sku}: {map_err}")
                    # update the minimum quantity and new calculated price on Ebay for all items
                    response = complete_enrollment_quantity_price_update_on_ebay(userid, item.market_item_id, selling_price, market_enrolled.maximum_quantity, market_enrolled._id)
                    if "Success" in response:
                        item_to_save, created = MarketPlaceUpdateLog.objects.update_or_create(user_id=userid, inventory_id=item.id, defaults=dict(market_name="Ebay", vendor_name=item.vendor_name, updated_sku=item.sku, log_description=f"Updated price to {selling_price} and quantity to {market_enrolled.maximum_quantity} from vendor {item.vendor_name}"))
                          
                inventory, created = InventoryModel.objects.update_or_create(user_id=userid, id=item.id, defaults=dict(start_price=selling_price, last_updated=timezone.now()))
        except Exception as e:
            print(f"Failed to update items selling price for user: {userid} with sku: {item.sku}. Error: {e}")
            continue



