import json, requests, time
import base64
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from ebaysdk.exception import ConnectionError
from .models import InventoryModel
from xml.etree import ElementTree as ET
from marketplaceApp.views import Ebay
from vendorEnrollment.models import CwrUpdate, FragrancexUpdate, LipseyUpdate, RsrUpdate, SsiUpdate, ZandersUpdate, Generalproducttable, Enrollment
from marketplaceApp.models import MarketplaceEnronment
from ratelimit import limits, sleep_and_retry
from django.db.models import Q
from woocommerce import API


# Create a function to update items quantity and price at the background on Ebay
def update_items_quantity_or_price_on_ebay(access_token, item_id, price, quantity, market_id):
    # eBay Trading API endpoint
    url = 'https://api.ebay.com/ws/api.dll'

    headers = {
        'X-EBAY-API-CALL-NAME': 'ReviseItem',
        'X-EBAY-API-SITEID': '0',  # Change this to your site ID, 0 is for US
        'X-EBAY-API-COMPATIBILITY-LEVEL': '1081',  # eBay API version
        'Content-Type': 'text/xml',
        'Authorization': f'Bearer {access_token}'
    }
    user_data = MarketplaceEnronment.objects.get(_id=market_id, marketplace_name="Ebay")
    try:
        # XML Body for ReviseItem request
        if user_data.enable_price_update == True and user_data.enable_quantity_update == True:
            body = f"""
            <?xml version="1.0" encoding="utf-8"?>
            <ReviseItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
                <RequesterCredentials>
                    <eBayAuthToken>{access_token}</eBayAuthToken>
                </RequesterCredentials>
                <Item>
                    <ItemID>{item_id}</ItemID>
                    <StartPrice>{price,}</StartPrice>
                    <Quantity>{quantity}</Quantity>
                </Item>
            </ReviseItemRequest>
            """
        elif user_data.enable_price_update == True and user_data.enable_quantity_update == False:
            body = f"""
            <?xml version="1.0" encoding="utf-8"?>
            <ReviseItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
                <RequesterCredentials>
                    <eBayAuthToken>{access_token}</eBayAuthToken>
                </RequesterCredentials>
                <Item>
                    <ItemID>{item_id}</ItemID>
                    <StartPrice>{price}</StartPrice>
                </Item>
            </ReviseItemRequest>
            """
        elif user_data.enable_price_update == False and user_data.enable_quantity_update == True:
            body = f"""
            <?xml version="1.0" encoding="utf-8"?>
            <ReviseItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
                <RequesterCredentials>
                    <eBayAuthToken>{access_token}</eBayAuthToken>
                </RequesterCredentials>
                <Item>
                    <ItemID>{item_id}</ItemID>
                    <Quantity>{quantity}</Quantity>
                </Item>
            </ReviseItemRequest>
            """
        else:
            return None
        
        # Make the POST request
        response = requests.post(url, headers=headers, data=body)
        # Check the response
        if response.status_code == 200:
            return f"Success: {response.text}"
        else:
            return f"Error:{response.text}"
    except ConnectionError as e:
        return f'Error: {e}'


# Get all products already listed on Ebay using sku
def get_all_items_on_ebay(user_id):
    eb = Ebay()
    ebay_items = []
    page_number = 1
    total_pages = 1  # Initialize to 1 to enter the loop
    access_token = eb.refresh_access_token(user_id, "Ebay")
    print(f"Access token in inventoryApp utils: {access_token}")
    if not access_token:
        print(f"Failed to refresh access token. Access token returns none in marketplace id: {user_id}")   
        return None
    try:
        url = "https://api.ebay.com/ws/api.dll"
        headers = {
            "X-EBAY-API-CALL-NAME": "GetMyeBaySelling",
            "X-EBAY-API-SITEID": "0",
            "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
            "X-EBAY-API-IAF-TOKEN": access_token,
            "Content-Type": "text/xml"
        }
        namespace = {'ebay': 'urn:ebay:apis:eBLBaseComponents'}

        while page_number <= total_pages:
            items = []
            # XML request body for the GetMyeBaySelling API with current page number
            body = f"""<?xml version="1.0" encoding="utf-8"?>
                    <GetMyeBaySellingRequest xmlns="urn:ebay:apis:eBLBaseComponents">
                        <RequesterCredentials>
                            <eBayAuthToken>{access_token}</eBayAuthToken>
                        </RequesterCredentials>
                        <ActiveList>
                            <Pagination>
                                <EntriesPerPage>100</EntriesPerPage>
                                <PageNumber>{page_number}</PageNumber>
                            </Pagination>
                        </ActiveList>
                    </GetMyeBaySellingRequest>"""
                        
            # Sending the request
            response = requests.post(url, headers=headers, data=body)               
            if response.status_code == 200:
                # Decode response content if it's in byte format
                xml_content = response.content.decode('utf-8')
                
                # Parsing the XML response
                root = ET.fromstring(xml_content)

                # Get the total number of pages from the response
                total_pages_element = root.find(".//ebay:PaginationResult/ebay:TotalNumberOfPages", namespaces=namespace)
                if total_pages_element is not None:
                    total_pages = int(total_pages_element.text)                   

                # Loop through each item in the current page
                for item in root.findall(".//ebay:ItemArray/ebay:Item", namespaces=namespace):
                    item_id = item.find("ebay:ItemID", namespaces=namespace).text if item.find("ebay:ItemID", namespaces=namespace) is not None else "Not Found"
                    sku = item.find("ebay:SKU", namespaces=namespace).text if item.find("ebay:SKU", namespaces=namespace) is not None else "N/A"
                    title = item.find("ebay:Title", namespaces=namespace).text if item.find("ebay:Title", namespaces=namespace) is not None else "No Title"
                    price = item.find("ebay:SellingStatus/ebay:CurrentPrice", namespaces=namespace).text if item.find("ebay:SellingStatus/ebay:CurrentPrice", namespaces=namespace) is not None else "No Price"
                    quantity = item.find("ebay:Quantity", namespaces=namespace).text if item.find("ebay:Quantity", namespaces=namespace) is not None else "0"
                    quantity_sold = item.find("ebay:SellingStatus/ebay:QuantitySold", namespaces=namespace).text if item.find("ebay:SellingStatus/ebay:QuantitySold", namespaces=namespace) is not None else "0"
                    ListingDuration = item.find("ebay:ListingDuration", namespaces=namespace).text if item.find("ebay:ListingDuration", namespaces=namespace) is not None else "N/A"
                    Listingtype = item.find("ebay:ListingType", namespaces=namespace).text if item.find("ebay:ListingType", namespaces=namespace) is not None else "N/A"
                    PictureDetails = item.find("ebay:PictureDetails/ebay:GalleryURL", namespaces=namespace).text if item.find("ebay:PictureDetails/ebay:GalleryURL", namespaces=namespace) is not None else "N/A"
                    ShippingProfileID = item.find("ebay:SellerProfiles/ebay:SellerShippingProfile/ebay:ShippingProfileID", namespaces=namespace).text if item.find("ebay:SellerProfiles/ebay:SellerShippingProfile/ebay:ShippingProfileID", namespaces=namespace) is not None else "N/A"
                    ShippingProfileName = item.find("ebay:SellerProfiles/ebay:SellerShippingProfile/ebay:ShippingProfileName", namespaces=namespace).text if item.find("ebay:SellerProfiles/ebay:SellerShippingProfile/ebay:ShippingProfileName", namespaces=namespace) is not None else "N/A"
                    ReturnProfileID = item.find("ebay:SellerProfiles/ebay:SellerReturnProfile/ebay:ReturnProfileID", namespaces=namespace).text if item.find("ebay:SellerProfiles/ebay:SellerShippingProfile/ebay:ShippingProfileID", namespaces=namespace) is not None else "N/A"
                    ReturnProfileName = item.find("ebay:SellerProfiles/ebay:SellerReturnProfile/ebay:ReturnProfileName", namespaces=namespace).text if item.find("ebay:SellerProfiles/ebay:SellerShippingProfile/ebay:ShippingProfileName", namespaces=namespace) is not None else "N/A"
                    PaymentProfileID = item.find("ebay:SellerProfiles/ebay:SellerPaymentProfile/ebay:PaymentProfileID", namespaces=namespace).text if item.find("ebay:SellerProfiles/ebay:SellerPaymentProfile/ebay:PaymentProfileID", namespaces=namespace) is not None else "N/A"
                    PaymentProfileName = item.find("ebay:SellerProfiles/ebay:SellerPaymentProfile/ebay:PaymentProfileName", namespaces=namespace).text if item.find("ebay:SellerProfiles/ebay:SellerPaymentProfile/ebay:PaymentProfileName", namespaces=namespace) is not None else "N/A"

                    items.append([item_id, sku, title, price, quantity, ListingDuration, Listingtype, PictureDetails, ShippingProfileID, ShippingProfileName, ReturnProfileID, ReturnProfileName, PaymentProfileID, PaymentProfileName])


            # If no more items, break out of the loop
            if not items:
                break

            # Add retrieved items to the list
            ebay_items.extend(items)
        
            # Increment the page number for the next iteration
            page_number += 1
            
    except Exception as e:
        print(f"Failed to get products: {e}")
    
    return ebay_items
    
# Function to get details of specific item listing on ebay
# Limit to 5 calls per second (eBay's typical limit)
@sleep_and_retry
@limits(calls=5, period=1)
def get_item_details(user_id, item_id):
    """Fetch detailed product information (UPC, EAN, Brand, etc.) using GetItem API."""
    eb = Ebay()
    access_token = eb.refresh_access_token(user_id, "Ebay")
    if not access_token:
        print(f"Failed to refresh access token. Access token returns none in marketplace id: {user_id}")   
        return None
    
    # Set up the headers with the access token
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    # get full product details of the item in inventory
    try:
        item_url = f"https://api.ebay.com/buy/browse/v1/item/get_item_by_legacy_id?legacy_item_id={item_id}"
        response = requests.get(item_url, headers=headers)
        if response.status_code == 429:  # Rate limit hit
            retry_after = int(response.headers.get('Retry-After', 2))
            time.sleep(retry_after)
            return get_item_details(access_token, item_id)
    
        product_data = response.json()
        if response.status_code == 200:
            return product_data
        else:
            print(f"Failed to retrieve details for inventory for Item ID {item_id}: {response.text}")
            return None
    except Exception as e:
        print(f"Failed to retrieve item details for inventory: {e}")
        return None
            

# Calculate the selling price of product going to ebay
def calculated_selling_price(enroll_id, market_id, start_price, userid, map=""):
    try:
        market_place = MarketplaceEnronment.objects.get(_id=market_id)
        enrollment = get_object_or_404(Enrollment, id=enroll_id, user_id=userid)
        total_product_cost = float(start_price) + float(enrollment.fixed_markup) + ((int(enrollment.percentage_markup)/100) * float(start_price))
        selling_price = total_product_cost + float(market_place.fixed_markup) + ((float(market_place.fixed_percentage_markup)/100) * total_product_cost) + ((float(market_place.profit_margin)/100) * total_product_cost)
        if map:
            if selling_price < float(map):
                selling_price = float(map)
    except Exception as e:
        print(f"Failed to compute price due to missing data with user id {userid}, enroll_id {enroll_id}, start_price {start_price}: {e}")
        return None

    return round(selling_price, 2), round(total_product_cost, 2)


# Get all existing listed products on Woocommerce store.
def get_woocommerce_existing_products(user_id):
    enrollment = MarketplaceEnronment.objects.get(user_id=user_id, marketplace_name="Woocommerce")
    # Set up the WooCommerce API client
    wcapi = API(
        url = enrollment.wc_consumer_url, 
        consumer_key = enrollment.wc_consumer_key,  
        consumer_secret = enrollment.wc_consumer_secret, 
        version = "wc/v3"
    )
    products = wcapi.get("products").json()  
    return products


# Function to update product on woocommerce store
def update_woocommerce_product_from_background(market_item_id, selling_price, quantity, userid):
    try:
        enrollment = MarketplaceEnronment.objects.get(user_id=userid, marketplace_name="Woocommerce")
        # Set up the WooCommerce API client
        wcapi = API(
            url = enrollment.wc_consumer_url, 
            consumer_key = enrollment.wc_consumer_key,  
            consumer_secret = enrollment.wc_consumer_secret, 
            version = "wc/v3"
        )
        # Product payload mapped to WooCommerce
        update_data = {
            "type": "simple",
            "regular_price": selling_price,
            "stock_quantity": quantity,
            "manage_stock": True,
        }

        # --- MAKE THE UPDATE REQUEST ---
        response = wcapi.put(f"products/{market_item_id}", update_data)
        if response.status_code == 200:
            return "Success"
        else:
            print("Error: Woocommerce update fails.")
    except Exception as e:
        print("Error: Error from the try block woocommerce update.")
        return None

# Map items on ebay with the one on local database for updates
# @api_view(['GET'])
def sync_ebay_items_with_local():
    eb = Ebay()
    all_ebay_items = []
    db_items = None
    # Get all user with ebay marketplace to sync their products
    user_token = MarketplaceEnronment.objects.all() # get all user to get their access_token
    for user in user_token:
        if user.marketplace_name == "Ebay":
            # Fetch all item from eBay
            ebay_items = get_all_items_on_ebay(user.user_id)
            for item in ebay_items:
                all_ebay_items.append({"ebay_item_id":item[0], "ebay_sku":item[1], 'Title':item[2], "ebay_price":item[3], "ebay_quantity":item[4], 'ListingDuration':item[5], 'ListingType':item[6], 'PictureDetails':item[7], 'ShippingProfileID':item[8], 'ShippingProfileName':item[9], 'ReturnProfileID':item[10], 'ReturnProfileName':item[11], 'PaymentProfileID':item[12], 'PaymentProfileName':item[13]})
            for item in all_ebay_items:
                try:
                    item_exists = InventoryModel.objects.filter(Q(market_item_id=item.get("ebay_item_id")) | Q(sku=item.get("ebay_sku")))[0]
                    # Fetch the item from the local vendor's table
                    vendor_list = ["FragrancexUpdate", "CwrUpdate", "LipseyUpdate", "RsrUpdate", "SsiUpdate", "ZandersUpdate"]
                    for vendor_db in vendor_list:
                        try:
                            # Get the actual model class from the string name
                            model_class = globals()[vendor_db]
                            db_items = model_class.objects.filter(Q(sku=item.get("ebay_sku")) & (Q(mpn=item_exists.mpn) | Q(upc=item_exists.upc)))
                            if not db_items.exists():
                                continue
                            
                            db_item = None                  
                            # Ensure the item belongs to the same user we are processing currently
                            for item_match in db_items:
                                enrollment = Enrollment.objects.get(id=item_match.enrollment_id)
                                if enrollment.user_id == user.user_id:
                                    db_item = item_match
                                    print(f'product found for vendor: {vendor_db}')
                                    break

                            break                    
                        except Exception as ea:
                            continue

                    if db_item:
                        try:
                            # Modify selling price before updating on ebay 
                            cost_computation = calculated_selling_price(enroll_id=db_item.enrollment_id, market_id=user._id, start_price=db_item.total_price, userid=user.user_id, map=db_item.product.map)
                            if cost_computation == None:
                                continue
                            selling_price, total_product_cost = cost_computation
                            # Create or update the product on GeneralProduct table
                            item_product, created = Generalproducttable.objects.update_or_create(user_id=user.user_id, sku=db_item.sku, defaults=dict(active=True, total_product_cost=total_product_cost, upc=item_exists.upc, map=db_item.product.map, mpn=item_exists.mpn, enrollment_id=db_item.enrollment_id, product_id=db_item.product_id, quantity=db_item.quantity, price=db_item.total_price, vendor_name=db_item.vendor.name))
                            # Item exists, check if we need to update price or quantity
                            InventoryModel.objects.filter(Q(market_item_id=item.get("ebay_item_id")) | Q(sku=item.get("ebay_sku"))).update(start_price=selling_price, quantity=db_item.quantity, total_product_cost=total_product_cost, map_status=True, product_id=item_product.id, market_item_id=item.get("ebay_item_id"), vendor_name=db_item.vendor.name)
                            # Update the VendorUpdate table to set listed_market to true
                            db_item.active = True
                            db_item.save()
                            
                            # Check if there is a price and quantity update, then update on Ebay
                            # if item["ebay_price"] != selling_price or item["ebay_quantity"] != db_item.quantity:
                            #     # Update the product on Ebay
                            #     response = update_items_quantity_or_price_on_ebay(access_token, item["ebay_item_id"], selling_price, db_item.quantity, user._id)
                            #     print("product updated on ebay successful.")
                            db_items = None
                        except Exception as e:
                            print(f"Product processing failed with error: {e}")
                            continue
                        
                except Exception as e:
                    # If item does not exist, insert new item
                    try:
                        # Get product details from eBay
                        product_details = get_item_details(user.user_id, item.get("ebay_item_id"))
                        if product_details == None:
                            continue
                        else:
                            # Get the upc and also mpn if no main mpn field does not exist
                            for specific in product_details.get("localizedAspects"):
                                ebay_upc = specific.get("value") if specific.get("name") == "UPC" else ""
                                ebay_mpn = specific.get("value") if specific.get("name") == "MPN" else product_details.get("mpn")

                        item_to_save, created = InventoryModel.objects.update_or_create(user_id=user.user_id, market_item_id=item.get("ebay_item_id"), defaults=dict(
                            title=item.get("Title"), description=json.dumps(product_details.get("shortDescription")), location=product_details.get("itemLocation")["country"], category_id=product_details.get("categoryId"), sku=item.get("ebay_sku"), upc=ebay_upc, mpn=ebay_mpn, start_price=product_details.get("price")["value"], picture_detail=product_details.get("image")["imageUrl"], postal_code=product_details.get("itemLocation")["postalCode"], quantity=item.get("ebay_quantity"), return_profileID=item.get('ReturnProfileID'), return_profileName=item.get('ReturnProfileName'), payment_profileID=item.get('PaymentProfileID'), payment_profileName=item.get('PaymentProfileName'), shipping_profileID=item.get('ShippingProfileID'), shipping_profileName=item.get('ShippingProfileName'), bestOfferEnabled=True, listingType=item.get('ListingType'),
                            gift="", categoryMappingAllowed="", item_specific_fields=product_details.get("localizedAspects"), market_logos=product_details.get("listingMarketplaceId"),  market_item_id=item.get("ebay_item_id"), user_id=user.user_id, date_created=product_details.get("itemCreationDate").split("T")[0], active=True, category=product_details.get("categoryPath"), city=product_details.get("itemLocation")["city"], cost=product_details.get("price")["value"], country=product_details.get("itemLocation")["country"], price=product_details.get("price")["value"], thumbnailImage=product_details.get("additionalImages"), vendor_name="Not Found", map_status=False))

                    except Exception as e:
                        print(f"Ebay Product failed to insert into inventory {e}")

        elif user.marketplace_name == "Woocommerce":
            # Fetch all item from Woocommerce
            all_woocommercer_items = get_woocommerce_existing_products(user.user_id)
            for item in all_woocommercer_items:
                try:
                    item_exists = InventoryModel.objects.filter(Q(market_item_id=item.get("id")) | Q(sku=item.get("sku")))[0]
                    # Fetch the item from the local vendor's table
                    vendor_list = ["FragrancexUpdate", "CwrUpdate", "LipseyUpdate", "RsrUpdate", "SsiUpdate", "ZandersUpdate"]
                    for vendor_db in vendor_list:
                        try:
                            # Get the actual model class from the string name
                            model_class = globals()[vendor_db]
                            db_items = model_class.objects.filter(Q(sku=item.get("sku")))
                            if not db_items.exists():
                                continue
                            
                            db_item = None                  
                            # Ensure the item belongs to the same user we are processing currently
                            for item_match in db_items:
                                enrollment = Enrollment.objects.get(id=item_match.enrollment_id)
                                if enrollment.user_id == user.user_id:
                                    db_item = item_match
                                    print(f'product found for vendor: {vendor_db}')
                                    break

                            break                    
                        except Exception as ea:
                            continue

                    if db_item:
                        try:
                            # Modify selling price before updating on ebay 
                            cost_computation = calculated_selling_price(enroll_id=db_item.enrollment_id, market_id=user._id, start_price=db_item.total_price, userid=user.user_id, map=db_item.product.map)
                            if cost_computation == None:
                                continue
                            selling_price, total_product_cost = cost_computation
                            # Create or update the product on GeneralProduct table
                            item_product, created = Generalproducttable.objects.update_or_create(user_id=user.user_id, sku=db_item.sku, defaults=dict(active=True, total_product_cost=total_product_cost, map=db_item.product.map, enrollment_id=db_item.enrollment_id, product_id=db_item.product_id, quantity=db_item.quantity, price=db_item.total_price, vendor_name=db_item.vendor.name))
                            # Item exists, check if we need to update price or quantity
                            InventoryModel.objects.filter(Q(market_item_id=item.get("id")) | Q(sku=item.get("sku"))).update(start_price=selling_price, quantity=db_item.quantity, total_product_cost=total_product_cost, map_status=True, product_id=item_product.id, market_item_id=item.get("id"), vendor_name=db_item.vendor.name)
                            # Update the VendorUpdate table to set listed_market to true
                            db_item.active = True
                            db_item.save()
                            
                            # Check if there is a price and quantity update, then update on Ebay
                            if item["price"] != selling_price or item["quantity"] != db_item.quantity:
                                # Update the product on WooCommerce
                                response = update_woocommerce_product_from_background(item["id"], selling_price, db_item.quantity, user.user_id)
                                print("product updated on woocommerce successful.")
                            db_items = None
                        except Exception as e:
                            print(f"Product processing failed with error: {e}")
                            continue
                except Exception as e:
                    # If item does not exist, insert new item
                    try:
                        item_to_save, created = InventoryModel.objects.update_or_create(user_id=user.user_id, market_item_id=item.get("id"), defaults=dict(title=item.get("name"), description=json.dumps(item.get("description")), category_id=112233, sku=item.get("sku"), start_price=item.get("price"), picture_detail="", quantity=item.get("quantity"), return_profileID="Null", return_profileName="Null", payment_profileID="Null", payment_profileName="Null", shipping_profileID="Null", shipping_profileName="Null", categoryMappingAllowed="", item_specific_fields="Null", market_logos="Null", market_item_id=item.get("id"), user_id=user.user_id, date_created=item.get("date_created"), active=True, category="", price=item.get("price"), thumbnailImage="Null", vendor_name="Not Found", enable_charity=True, woo_category_name="", market_name="Woocommerce", map_status=False))

                    except Exception as e:
                        print(f"Woocommerce Product failed to insert into inventory {e}")
                


