import json, requests, time
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from ebaysdk.exception import ConnectionError
from .models import InventoryModel, UpdateLogModel
from xml.etree import ElementTree as ET
from marketplaceApp.views import Ebay
from vendorEnrollment.models import CwrUpdate, FragrancexUpdate, LipseyUpdate, RsrUpdate, SsiUpdate, ZandersUpdate, Generalproducttable, Enrollment
from marketplaceApp.models import MarketplaceEnronment
from ratelimit import limits, sleep_and_retry
from django.db.models import Q
from woocommerce import API
from django.apps import apps


# Get all products already listed on Ebay using sku
def get_all_items_on_ebay(enroll_id):
    ebay_items = []
    page_number = 1
    total_pages = 1  # Initialize to 1 to enter the loop
    try:
        user_data = MarketplaceEnronment.objects.get(_id=enroll_id, marketplace_name="Ebay")
    except Exception as e:
        if e.get('errors')[0]['errorId'] == 1001:
            return None
        else:
            return "Error"
    
    access_token =  user_data.access_token
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
                    market_item_url = item.find("ebay:ListingDetails/ebay:ViewItemURL", namespaces=namespace).text if item.find("ebay:ListingDetails/ebay:ViewItemURL", namespaces=namespace) is not None else "N/A"

                    items.append([item_id, sku, title, price, quantity, ListingDuration, Listingtype, PictureDetails, ShippingProfileID, ShippingProfileName, ReturnProfileID, ReturnProfileName, PaymentProfileID, PaymentProfileName, market_item_url])


            # If no more items, break out of the loop
            if not items:
                break

            # Add retrieved items to the list
            ebay_items.extend(items)
        
            # Increment the page number for the next iteration
            page_number += 1

    except requests.exceptions.ConnectTimeout as e:
        return "Error"        
    except Exception as e:
        if e.get('errors')[0]['errorId'] == 1001:
            return None
        else:
            return "Error"
    
    return ebay_items
    
# Function to get details of specific item listing on ebay
# Limit to 5 calls per second (eBay's typical limit)
@sleep_and_retry
@limits(calls=5, period=1)
def get_item_details(enroll_id, item_id):
    """Fetch detailed product information (UPC, EAN, Brand, etc.) using GetItem API."""
    try:
        user_data = MarketplaceEnronment.objects.get(_id=enroll_id, marketplace_name="Ebay")
    except Exception as e:
        print(f"Failed to fetch access token")
        return None
    
    access_token =  user_data.access_token
    
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
            return "Error"
    except Exception as e:
        if e.get('errors')[0]['errorId'] == 1001:
            return None
        else:
            return "Error"
                    
        
# Calculate the selling price of product going to ebay
def calculated_selling_price(market_id, total_product_cost, userid, map=""):
    try:
        market_place = MarketplaceEnronment.objects.get(_id=market_id)
        selling_price = float(total_product_cost) + float(market_place.fixed_markup) + ((float(market_place.fixed_percentage_markup)/100) * float(total_product_cost)) + ((float(market_place.profit_margin)/100) * float(total_product_cost))
        if map:
            if selling_price < float(map):
                selling_price = float(map)
    except Exception as e:
        print(f"Failed to compute price due to missing data with user id {userid}, total_product_cost {total_product_cost}: {e}")
        return None

    return round(selling_price, 2), round(total_product_cost, 2)


# Get all existing listed products on Woocommerce store for a specific user.
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


# An helper function to filter product by upc or mpn and sku
def query_product_filter(upc=None, mpn=None):
    # Ensure at least one identifier is provided
    if not upc and not mpn:
        raise ValueError("Either UPC or SKU must be provided to activate a product.")
    conditions = Q()
    if upc:
        conditions |= Q(upc=upc)
    if mpn:
        conditions |= Q(sku=mpn)

    return conditions


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
            ebay_items = get_all_items_on_ebay(user._id)
            # If fetching items failed due to invalid token, try refreshing token once and fetch again
            if ebay_items == None:
                token = eb.refresh_access_token(user.user_id, "Ebay")
                ebay_items = get_all_items_on_ebay(user._id)
            elif ebay_items == "Error":
                print(f"Failed to fetch all items from ebay for user {user.user_id}.")
                continue
            
            for item in ebay_items:
                all_ebay_items.append({"ebay_item_id":item[0], "ebay_sku":item[1], 'Title':item[2], "ebay_price":item[3], "ebay_quantity":item[4], 'ListingDuration':item[5], 'ListingType':item[6], 'PictureDetails':item[7], 'ShippingProfileID':item[8], 'ShippingProfileName':item[9], 'ReturnProfileID':item[10], 'ReturnProfileName':item[11], 'PaymentProfileID':item[12], 'PaymentProfileName':item[13]})
            for item in all_ebay_items:
                try:
                    # verify if item already existing on inventory
                    item_exists = InventoryModel.objects.get(user_id=user.user_id, market_item_id=item.get("ebay_item_id"))
                   
                   # Get list of vendors registered by the user
                    enrollment = Enrollment.objects.filter(user_id=user.user_id)
                    vendor_list = [vendor_name.vendor.name.capitalize() for vendor_name in enrollment]

                    for vendor_db in vendor_list:
                        try:
                            model_name = vendor_db + "Update"
                            # Get the actual model class from the string name
                            model_class = apps.get_model('vendorEnrollment', model_name)
                            conditions = query_product_filter(item_exists.upc, item_exists.mpn)
                            db_items = model_class.objects.filter(conditions & Q(sku=item.get("ebay_sku")))
                            if not db_items.exists():
                                continue
                            
                            db_item = db_items[0]        
                            break                    
                        except Exception as ea:
                            continue

                    if db_item:
                        try:
                            # Modify selling price before updating on ebay 
                            cost_computation = calculated_selling_price(market_id=user._id, total_product_cost=db_item.total_price, userid=user.user_id, map=db_item.map)
                            if cost_computation == None:
                                continue
                            selling_price, total_product_cost = cost_computation
                            # Check if the product exists in GeneralProduct table
                            item_product = Generalproducttable.objects.filter(user_id=user.user_id, id=item_exists.product_id)
                            if not item_product.exists():
                                item_product = Generalproducttable.objects.create(user_id=user.user_id, sku=db_item.sku, upc=db_item.upc, mpn=db_item.mpn, active=True, total_product_cost=total_product_cost, map=db_item.product.map, enrollment_id=db_item.enrollment_id, product_id=db_item.product_id, quantity=db_item.quantity, price=db_item.total_price, vendor_name=db_item.vendor.name)
                            # Item exists, check if we need to update price or quantity
                            inventory, created = InventoryModel.objects.update_or_create(market_item_id=item.get("ebay_item_id"), user_id=user.user_id, defaults={"map_status": True, "product_id": item_product.id, "vendor_name": db_item.vendor.name, "market_item_url": item.get("market_item_url")})
                            # Update the VendorUpdate table to set listed_market to true
                            db_item.active = True
                            db_item.save()
                            
                            db_items = None
                        except Exception as e:
                            print(f"Ebay Product processing failed with error: {e}")
                            continue
                        
                except Exception as e:
                    print(f"Ebay Product processing in first try block failed: {e}")
                    # If item does not exist, insert new item
                    try:
                        # Get product details from eBay
                        product_details = get_item_details(user._id, item.get("ebay_item_id"))
                        if product_details == None:
                            # If fetching items failed due to invalid token, try refreshing token once and fetch again
                            token = eb.refresh_access_token(user.user_id, "Ebay")
                            product_details = get_item_details(user._id, item.get("ebay_item_id"))
                        elif product_details == "Error":
                            print(f"Failed to fetch item details from ebay for item {item.get('ebay_item_id')} for user {user.user_id}.")
                            continue
                        else:
                            # Get the upc and mpn if no main mpn field does not exist
                            for specific in product_details.get("localizedAspects"):
                                ebay_upc = specific.get("value") if specific.get("name") == "UPC" else ""
                                ebay_mpn = specific.get("value") if specific.get("name") == "MPN" else product_details.get("mpn")

                        inentory, created = InventoryModel.objects.update_or_create(user_id=user.user_id, market_item_id=item.get("ebay_item_id"), defaults={"title": item.get("Title"),"description": json.dumps(product_details.get("shortDescription")), "location": product_details.get("itemLocation")["country"], "category_id": product_details.get("categoryId"), "category": product_details.get("categoryPath"), "sku": item.get("ebay_sku"), "upc": ebay_upc, "mpn": ebay_mpn, "start_price": product_details.get("price")["value"], "price": product_details.get("price")["value"], "cost": product_details.get("price")["value"], "picture_detail": product_details.get("image")["imageUrl"], "thumbnailImage": product_details.get("additionalImages"), "postal_code": product_details.get("itemLocation")["postalCode"], "city": product_details.get("itemLocation")["city"], "country": product_details.get("itemLocation")["country"], "quantity": item.get("ebay_quantity"), "return_profileID": item.get("ReturnProfileID"), "return_profileName": item.get("ReturnProfileName"), "payment_profileID": item.get("PaymentProfileID"), "payment_profileName": item.get("PaymentProfileName"), "shipping_profileID": item.get("ShippingProfileID"), "shipping_profileName": item.get("ShippingProfileName"), "bestOfferEnabled": True, "listingType": item.get("ListingType"), "item_specific_fields": product_details.get("localizedAspects"), "market_logos": product_details.get("listingMarketplaceId"), "date_created": product_details.get("itemCreationDate").split("T")[0], "active": True, "vendor_name": "Not Found", "map_status": False, "market_name": "Ebay", "fixed_percentage_markup": user.fixed_percentage_markup, "fixed_markup": user.fixed_markup, "profit_margin": user.profit_margin, "min_profit_mergin": user.min_profit_mergin, "charity_id": user.charity_id, "enable_charity": user.enable_charity, "market_item_url": item.get("market_item_url")})



                    except Exception as e:
                        print(f"Ebay Product failed to insert into inventory {e}")

        elif user.marketplace_name == "Woocommerce":
            # Fetch all item from Woocommerce
            all_woocommercer_items = get_woocommerce_existing_products(user.user_id)
            for item in all_woocommercer_items:
                try:
                    # verify if item already existing on inventory
                    item_exists = InventoryModel.objects.get(user_id=user.user_id, market_item_id=item.get("id"))

                    # Get list of vendors registered by the user
                    enrollment = Enrollment.objects.filter(user_id=user.user_id)
                    vendor_list = [vendor_name.vendor.name.capitalize() for vendor_name in enrollment]
                    for vendor_db in vendor_list:
                        try:
                            model_name = vendor_db + "Update"
                            # Get the actual model class from the string name
                            model_class = apps.get_model('vendorEnrollment', model_name)
                            conditions = query_product_filter(item_exists.upc, item_exists.mpn)
                            db_items = model_class.objects.filter(conditions & Q(sku=item.get("sku")))
                            if not db_items.exists():
                                continue
                            
                            db_item = db_items[0]                 
                            break                    
                        except Exception as ea:
                            continue

                    if db_item:
                        try:
                            # Modify selling price before updating on ebay 
                            cost_computation = calculated_selling_price(market_id=user._id, total_product_cost=db_item.total_price, userid=user.user_id, map=db_item.map)
                            if cost_computation == None:
                                continue
                            selling_price, total_product_cost = cost_computation
                            # Check if the product exists in GeneralProduct table
                            item_product = Generalproducttable.objects.filter(user_id=user.user_id, id=item_exists.product_id)
                            if not item_product.exists():
                                item_product = Generalproducttable.objects.create(user_id=user.user_id, sku=db_item.sku, upc=db_item.upc, mpn=db_item.mpn, active=True, total_product_cost=total_product_cost, map=db_item.product.map, enrollment_id=db_item.enrollment_id, product_id=db_item.product_id, quantity=db_item.quantity, price=db_item.total_price, vendor_name=db_item.vendor.name)
                            # insert mapped item into inventory
                            inentory, created = InventoryModel.objects.update_or_create(market_item_id=item.get("id"), user_id=user.user_id, defaults={"map_status": True, "product_id": item_product.id, "vendor_name": db_item.vendor.name, "market_item_url": item.get("market_item_url")})
                            # Update the VendorUpdate table to set listed_market to true
                            db_item.active = True
                            db_item.save()
                            
                            db_items = None
                        except Exception as e:
                            print(f" Woocommerce Product processing failed with error: {e}")
                            continue
                except Exception as e:
                    print(f" Woocommerce Product processing in first try block failed: {e}")
                    # If item does not exist, insert new item
                    try:
                        categories = item.get("categories") or []
                        category_id = categories[0]["id"] if categories and "id" in categories[0] else 0
                        category_name = categories[0].get("name") if categories else "NA"
                        images = item.get("images") or []
                        picture_url = images[0].get("src") if images else "NA"
                        item_to_save, created = InventoryModel.objects.update_or_create(user_id=user.user_id, market_item_id=item.get("id"), defaults=dict(title=item.get("name") or "NA", description=json.dumps(item.get("description")) or "NA", category_id=category_id, category=category_name, woo_category_name=category_name, sku=item.get("sku") or 0,  start_price=item.get("price") or 0, price=item.get("price") or 0, picture_detail=picture_url, thumbnailImage="Null", quantity=item.get("stock_quantity") or 0, return_profileID="Null", return_profileName="Null", payment_profileID="Null", payment_profileName="Null", shipping_profileID="Null", shipping_profileName="Null", categoryMappingAllowed="", item_specific_fields="Null", market_logos="Null", date_created=(item.get("date_created") or "NA").split("T")[0], active=True, vendor_name="Not Found", enable_charity=True, market_name="Woocommerce", map_status=False, fixed_percentage_markup=user.fixed_percentage_markup, fixed_markup=user.fixed_markup, profit_margin=user.profit_margin, min_profit_mergin=user.min_profit_mergin,  market_item_url=item.get("permalink") or "NA"))

                    except Exception as e:
                        print(f"Woocommerce Product failed to insert into inventory {e}")
                


