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
    eb = Ebay()
    ebay_items = []
    page_number = 1
    total_pages = 1  # Initialize to 1 to enter the loop
    try:
        user_data = MarketplaceEnronment.objects.get(_id=enroll_id, marketplace_name="Ebay")
    except Exception as e:
        print(f"Failed to fetch access token {e}")
        return None

    
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
                    item_market_url = item.find(".//ebay:ViewItemURL", namespaces=namespace).text if item.find(".//ebay:ViewItemURL", namespaces=namespace) is not None else "N/A"

                    items.append([item_id, sku, title, price, quantity, ListingDuration, Listingtype, PictureDetails, ShippingProfileID, ShippingProfileName, ReturnProfileID, ReturnProfileName, PaymentProfileID, PaymentProfileName, item_market_url])

  
            # If no more items, break out of the loop
            if not items:
                break

            # Add retrieved items to the list
            ebay_items.extend(items)
        
            # Increment the page number for the next iteration
            page_number += 1

    except requests.exceptions.ConnectTimeout as e:
        return None       
    except Exception as e:
        if e.get('errors')[0]['errorId'] == 1001:
            access_token = eb.refresh_access_token(user_data.user_id, "Ebay")
            get_all_items_on_ebay(enroll_id)
        else:
            return None
    
    return ebay_items
    
     
# Function to get details of specific item listing on ebay
# Limit to 5 calls per second (eBay's typical limit)
@sleep_and_retry
@limits(calls=5, period=1)
def get_item_details(enroll_id, item_id):
    eb = Ebay()
    """Fetch detailed product information (UPC, EAN, Brand, etc.) using GetItem API."""
    try:
        user_data = MarketplaceEnronment.objects.get(_id=enroll_id, marketplace_name="Ebay")
    except Exception as e:
        print(f"Failed to fetch access token {e}")
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
            return get_item_details(enroll_id, item_id)
    
        product_data = response.json()
        if response.status_code == 200:
            return product_data
        else:
            return None
            #  raise ValueError(product_data)
    except ValueError as e:
        error_data = e.args[0]  # The dict you passed into the exception

        if isinstance(error_data, dict) and error_data.get('errors'):
            if error_data['errors'][0].get('errorId') == 1001:
                access_token = eb.refresh_access_token(user_data.user_id, "Ebay")
                return get_item_details(enroll_id, item_id)  # return recursion call
            else:
                print(f"Error ID: {error_data['errors'][0].get('errorId')}")
                return None
        else:
            print("Unexpected error format:", error_data)
            return None



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



# Download all items from all marketplace to local inventory
def download_marketplace_items_to_inventory():
    all_ebay_items = []

    # Get all user with ebay marketplace to sync their products
    user_token = MarketplaceEnronment.objects.all() # get all user to get their access_token
    for user in user_token:
        # Deal with ebay marketplace
        if user.marketplace_name == "Ebay":
            # Fetch all item from eBay
            ebay_items = get_all_items_on_ebay(user._id)
            # If fetching items failed due to invalid token, try refreshing token once and fetch again
            if ebay_items == None:
                continue
            # Construct a list of ebay items with relevant details
            for item in ebay_items:
                all_ebay_items.append({"ebay_item_id":item[0], "ebay_sku":item[1], 'Title':item[2], "ebay_price":item[3], "ebay_quantity":item[4], 'ListingDuration':item[5], 'ListingType':item[6], 'PictureDetails':item[7], 'ShippingProfileID':item[8], 'ShippingProfileName':item[9], 'ReturnProfileID':item[10], 'ReturnProfileName':item[11], 'PaymentProfileID':item[12], 'PaymentProfileName':item[13], 'market_item_url':item[14]})
            
            for item in all_ebay_items:                         
                try:
                    # If item already exists, skip to next item
                    check_existing_item = InventoryModel.objects.filter(user_id=user.user_id, market_item_id=item.get("ebay_item_id"))
                    if check_existing_item.exists():
                        continue
                    # Get product details from eBay
                    product_details = get_item_details(user._id, item.get("ebay_item_id"))
                    if product_details == None:
                        continue
                    else:
                        # Get the upc and mpn if the main mpn field does not exist
                        for specific in product_details.get("localizedAspects"):
                            ebay_upc = specific.get("value") if specific.get("name") == "UPC" else ""
                            ebay_mpn = specific.get("value") if specific.get("name") == "MPN" else product_details.get("mpn") 

                        # Put all the custom fields in the dictionary
                        custom_fields = {}
                        for object in product_details.get("localizedAspects"):
                            custom_fields[object.get("name")] = object.get("value")
                            
                        inentory, created = InventoryModel.objects.update_or_create(user_id=user.user_id, market_item_id=item.get("ebay_item_id"), defaults={"title": item.get("Title"),"description": json.dumps(product_details.get("shortDescription")), "location": product_details.get("itemLocation")["country"], "category_id": product_details.get("categoryId"), "category": product_details.get("categoryPath"), "sku": item.get("ebay_sku"), "upc": ebay_upc, "mpn": ebay_mpn, "start_price": product_details.get("price")["value"], "price": product_details.get("price")["value"], "cost": product_details.get("price")["value"], "picture_detail": product_details.get("image")["imageUrl"], "thumbnailImage": product_details.get("additionalImages"), "postal_code": product_details.get("itemLocation")["postalCode"], "city": product_details.get("itemLocation")["city"], "country": product_details.get("itemLocation")["country"], "quantity": item.get("ebay_quantity"), "return_profileID": item.get("ReturnProfileID"), "return_profileName": item.get("ReturnProfileName"), "payment_profileID": item.get("PaymentProfileID"), "payment_profileName": item.get("PaymentProfileName"), "shipping_profileID": item.get("ShippingProfileID"), "shipping_profileName": item.get("ShippingProfileName"), "bestOfferEnabled": True, "listingType": item.get("ListingType"), "item_specific_fields": custom_fields, "market_logos": product_details.get("listingMarketplaceId"), "date_created": product_details.get("itemCreationDate").split("T")[0], "active": True, "vendor_name": "Not Found", "map_status": False, "market_name": "Ebay", "fixed_percentage_markup": user.fixed_percentage_markup, "fixed_markup": user.fixed_markup, "profit_margin": user.profit_margin, "min_profit_mergin": user.min_profit_mergin, "charity_id": user.charity_id, "enable_charity": user.enable_charity, "market_item_url": item.get("market_item_url")})
                
                except Exception as e:
                        print(f"Ebay Product failed to insert into inventory {e}")

        elif user.marketplace_name == "Woocommerce":
            # Fetch all item from Woocommerce
            all_woocommercer_items = get_woocommerce_existing_products(user.user_id)
            for item in all_woocommercer_items:
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
                


# Map items in inventory to products vendor update tables
def map_marketplace_items_to_vendor():
    # Get all user in with marketplace enrollment to map their products
    user_token = MarketplaceEnronment.objects.all()
    for user in user_token:
        # Get list of vendors registered by the user
        enrollment = Enrollment.objects.filter(user_id=user.user_id)
        vendor_list = [(vendor.vendor.name.capitalize(), vendor.id) for vendor in enrollment]
        # fetch all items from inventory for the user
        all_marketplace_items = InventoryModel.objects.filter(user_id=user.user_id, manual_map=False)
        for item in all_marketplace_items:
 
            # Find the product in vendor update tables
            for vendor_db in vendor_list:
                try:
                    vendor_db, enroll_id = vendor_db
                    model_name = vendor_db + "Update"
                    # Get the actual model class from the string name
                    model_class = apps.get_model('vendorEnrollment', model_name)
                    db_items = model_class.objects.get(((Q(sku=item.sku) & Q(upc=item.upc)) | (Q(sku=item.sku) & Q(mpn=item.mpn))), enrollment_id=enroll_id)
                
                    break                    
                except Exception as ea:
                    continue

            if db_items:
                try:
                    # Check if the product exists in GeneralProduct table
                    try:
                        item_product = Generalproducttable.objects.filter(user_id=user.user_id, id=item.product_id)
                        item_product = item_product[0]
                    except:
                        item_product = Generalproducttable.objects.create(user_id=user.user_id, sku=db_items.sku, upc=db_items.upc, mpn=db_items.mpn, active=True, total_product_cost=db_items.total_price, map=db_items.map, enrollment_id=db_items.enrollment_id, product_id=db_items.product_id, quantity=db_items.quantity, price=db_items.price, vendor_name=db_items.vendor.name)
                    
                    # Item exists, check if we need to update price or quantity
                    inventory, created = InventoryModel.objects.update_or_create(market_item_id=item.get("ebay_item_id"), user_id=user.user_id, defaults={"map_status": True, "product_id": item_product.id, "total_product_cost": db_items.total_price, "price": db_items.price, "vendor_name": db_items.vendor.name, "vendor_identifier": db_items.enrollment.identifier})
                    # Update the VendorUpdate table to set listed_market to true
                    db_items.active = True
                    db_items.save()
                    
                except Exception as e:
                            print(f"Ebay Product processing failed with error: {e}")
                            continue

