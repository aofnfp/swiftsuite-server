import json, requests, time, html
from django.utils import timezone
from .models import InventoryModel
from xml.etree import ElementTree as ET
from vendorEnrollment.models import CwrUpdate, FragrancexUpdate, LipseyUpdate, RsrUpdate, SsiUpdate, ZandersUpdate, Generalproducttable, Enrollment
from marketplaceApp.models import MarketplaceEnronment
from orderApp.models import OrdersOnEbayModel
from ratelimit import limits, sleep_and_retry
from django.db.models import Q
from woocommerce import API
from django.apps import apps
import logging
logger = logging.getLogger(__name__)



# Get all products already listed on Ebay using sku
def get_all_items_on_ebay(enroll_id):
    ebay_items = []
    page_number = 1
    total_pages = 1  # Initialize to 1 to enter the loop
    try:
        user_data = MarketplaceEnronment.objects.get(_id=enroll_id, marketplace_name="Ebay")  
        access_token = user_data.access_token
    except Exception as e:
        print(f"Failed to fetch access token {e}")
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
                    description = item.find('ebay:Description', namespaces=namespace).text if item.find('ebay:Description', namespaces=namespace) is not None else None
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
                    # Extract thumbnail images
                    images = [pic.text for pic in item.findall(".//ebay:PictureDetails/ebay:PictureURL", namespaces=namespace)] if item.findall(".//ebay:PictureDetails/ebay:PictureURL", namespaces=namespace) is not None else []
                    
                    items.append([item_id, sku, title, price, quantity, ListingDuration, Listingtype, PictureDetails, ShippingProfileID, ShippingProfileName, ReturnProfileID, ReturnProfileName, PaymentProfileID, PaymentProfileName, item_market_url, images, description])
            else:
                if response.json().get('errors')[0]['errorId'] == 1001:
                    return "access_token expired"
  
            # If no more items, break out of the loop
            if not items:
                break

            # Add retrieved items to the list
            ebay_items.extend(items)
        
            # Increment the page number for the next iteration
            page_number += 1

    except requests.exceptions.ConnectTimeout as e:
        return []      
    except Exception as e:
        return []
    
    return ebay_items
      

# Get full descriptions of the item from eBay using GetItem API, which has a rate limit of 5 calls per second
@sleep_and_retry
@limits(calls=5, period=1)
def get_item_specifics_from_ebay_for_item(enroll_id, item_id):
    """
    Live fetch of ItemSpecifics for an existing eBay listing via Trading API
    GetItem. Returns a dict of {aspect_name: value_string}, where multi-value
    aspects are joined with ", ". Returns {} on any failure.

    Used by `get_live_item_specifics` view to populate the edit page when
    the local InventoryModel.item_specific_fields is empty or stale.
    """
    try:
        user_data = MarketplaceEnronment.objects.get(_id=enroll_id, marketplace_name="Ebay")
        access_token = user_data.access_token
    except Exception as e:
        logger.info(f"get_item_specifics_from_ebay_for_item: no enrollment for {enroll_id}: {e}")
        return {}

    try:
        url = "https://api.ebay.com/ws/api.dll"
        headers = {
            "X-EBAY-API-CALL-NAME": "GetItem",
            "X-EBAY-API-SITEID": "0",
            "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
            "X-EBAY-API-IAF-TOKEN": access_token,
            "Content-Type": "text/xml",
        }
        body = f"""<?xml version="1.0" encoding="utf-8"?>
            <GetItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
              <ItemID>{item_id}</ItemID>
              <DetailLevel>ReturnAll</DetailLevel>
              <IncludeItemSpecifics>true</IncludeItemSpecifics>
            </GetItemRequest>"""
        response = requests.post(url, headers=headers, data=body, timeout=15)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 2))
            time.sleep(retry_after)
            return get_item_specifics_from_ebay_for_item(enroll_id, item_id)
        if response.status_code != 200:
            return {}

        ns = {"e": "urn:ebay:apis:eBLBaseComponents"}
        root = ET.fromstring(response.text)
        specifics = {}
        for nvl in root.findall(".//e:ItemSpecifics/e:NameValueList", ns):
            name = nvl.findtext("e:Name", default="", namespaces=ns)
            if not name:
                continue
            values = [(v.text or "") for v in nvl.findall("e:Value", ns)]
            specifics[name] = ", ".join(values) if len(values) > 1 else (values[0] if values else "")
        return specifics
    except requests.exceptions.RequestException as e:
        logger.info(f"get_item_specifics_from_ebay_for_item: request failed for item {item_id}: {e}")
        return {}
    except Exception as e:
        logger.info(f"get_item_specifics_from_ebay_for_item: parse failed for item {item_id}: {e}")
        return {}


def get_item_full_description(enroll_id, item_id):
    try:
        user_data = MarketplaceEnronment.objects.get(_id=enroll_id, marketplace_name="Ebay")
        access_token = user_data.access_token
    except Exception as e:
        print(f"Failed to fetch access token {e}")
        return None
    
    try:
        url = "https://api.ebay.com/ws/api.dll"

        headers = {
            "X-EBAY-API-CALL-NAME": "GetItem",
            "X-EBAY-API-SITEID": "0",
            "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
            "X-EBAY-API-IAF-TOKEN": access_token,
            "Content-Type": "text/xml"
        }

        body = f"""<?xml version="1.0" encoding="utf-8"?>
                <GetItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
                <ItemID>{item_id}</ItemID>
                <DetailLevel>ReturnAll</DetailLevel>
                <!-- IMPORTANT -->
                <IncludeItemSpecifics>true</IncludeItemSpecifics>
                <IncludeWatchCount>false</IncludeWatchCount>
                </GetItemRequest>
                """

        response = requests.post(url, headers=headers, data=body)
        if response.status_code == 429:  # Rate limit hit
            retry_after = int(response.headers.get('Retry-After', 2))
            time.sleep(retry_after)
            return get_item_full_description(enroll_id, item_id)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            description = root.findtext(
                ".//e:Description",
                default=None,
                namespaces={"e": "urn:ebay:apis:eBLBaseComponents"}
            )
        return description
    except requests.exceptions.ConnectTimeout as e:
        return None
    except Exception as e:
        return None

# Function to get details of specific item listing on ebay
# Limit to 5 calls per second (eBay's typical limit)
@sleep_and_retry
@limits(calls=5, period=1)
def get_item_details(enroll_id, item_id):
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
            
    except Exception as e:
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
def download_item_update_market_price_quantity():
    # Get all user with ebay marketplace to sync their products
    user_token = MarketplaceEnronment.objects.all() # get all user to get their access_token
    for user in user_token:
        all_ebay_items = []
        # Deal with ebay marketplace
        if user.marketplace_name == "Ebay":
            # Fetch all eBay items by walking backward
            ebay_downloaded_items = get_all_items_on_ebay(enroll_id=user._id)
            logger.info(f"Ebay inventory download fetched {len(ebay_downloaded_items)} items for user {user.user_id}")
            # If fetching items failed due to invalid token, try refreshing token once and fetch again
            if ebay_downloaded_items == None:
                logger.info(f"Ebay inventory download failed with error: {ebay_downloaded_items}")
                continue
            # Construct a list of ebay items with relevant details
            for item in ebay_downloaded_items:
                all_ebay_items.append({"ebay_item_id":item[0], "ebay_sku":item[1], 'Title':item[2], "ebay_price":item[3], "ebay_quantity":item[4], 'ListingDuration':item[5], 'ListingType':item[6], 'PictureDetails':item[7], 'ShippingProfileID':item[8], 'ShippingProfileName':item[9], 'ReturnProfileID':item[10], 'ReturnProfileName':item[11], 'PaymentProfileID':item[12], 'PaymentProfileName':item[13], 'market_item_url':item[14], 'images':item[15], 'description': item[16]})
            
            # Loop through each item and update or insert into InventoryModel
            for item in all_ebay_items:                         
                try:
                    # If item already exists, skip to next item
                    existing_item = InventoryModel.objects.get(user_id=user.user_id, market_item_id=item.get("ebay_item_id"))
                    # Update the market url on inventory
                    InventoryModel.objects.filter(user_id=user.user_id, id=existing_item.id).update(market_item_url=item.get("market_item_url"))
                except Exception as e:
                    try:
                        # Get product details from eBay
                        product_details = get_item_details(user._id, item.get("ebay_item_id"))
                        description = get_item_full_description(user._id, item.get("ebay_item_id"))
                        if product_details == None:
                            logger.info(f"Ebay get product details failed for item id {item.get('ebay_item_id')} with error: {product_details}")
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
                                
                            inentory, created = InventoryModel.objects.update_or_create(user_id=user.user_id, market_item_id=item.get("ebay_item_id"), defaults={"title": item.get("Title"),"description": json.dumps(description), "location": product_details.get("itemLocation")["country"], "category_id": product_details.get("categoryId"), "category": product_details.get("categoryPath"), "sku": item.get("ebay_sku"), "upc": ebay_upc, "mpn": ebay_mpn, "start_price": product_details.get("price")["value"], "price": product_details.get("price")["value"], "cost": product_details.get("price")["value"], "picture_detail": product_details.get("image")["imageUrl"], "thumbnailImage": product_details.get("additionalImages"), "postal_code": product_details.get("itemLocation")["postalCode"], "city": product_details.get("itemLocation")["city"], "country": product_details.get("itemLocation")["country"], "quantity": item.get("ebay_quantity"), "return_profileID": item.get("ReturnProfileID"), "return_profileName": item.get("ReturnProfileName"), "payment_profileID": item.get("PaymentProfileID"), "payment_profileName": item.get("PaymentProfileName"), "shipping_profileID": item.get("ShippingProfileID"), "shipping_profileName": item.get("ShippingProfileName"), "bestOfferEnabled": True, "listingType": item.get("ListingType"), "item_specific_fields": json.dumps(custom_fields), "market_logos": json.dumps({"Ebay": "https://i.postimg.cc/3xZSgy9Z/ebay.png"}), "date_created": product_details.get("itemCreationDate").split("T")[0], "active": True, "vendor_name": "Not Found", "map_status": False, "market_name": "Ebay", "fixed_percentage_markup": user.fixed_percentage_markup, "fixed_markup": user.fixed_markup, "profit_margin": user.profit_margin, "min_profit_mergin": user.min_profit_mergin, "charity_id": user.charity_id, "enable_charity": user.enable_charity, "market_item_url":item.get("market_item_url"), "thumbnailImage":item.get("images")})
                    except Exception as e:
                        logger.info(f"Ebay Product failed to insert into inventory {e}")


        elif user.marketplace_name == "Woocommerce":
            # Fetch all item from Woocommerce
            all_woocommercer_items = get_woocommerce_existing_products(user.user_id)
            try:
                for item in all_woocommercer_items:
                    # If item already exists, skip to next item
                    existing_item = InventoryModel.objects.get(user_id=user.user_id, market_item_id=item.get("id"))
                    InventoryModel.objects.filter(user_id=user.user_id, id=existing_item.id).update(market_item_url=item.get("permalink"))
            except Exception as e:
                try:
                    # If item does not exist, insert new item
                    categories = item.get("categories") or []
                    category_id = categories[0]["id"] if categories and "id" in categories[0] else 0
                    category_name = categories[0].get("name") if categories else "NA"
                    images = item.get("images") or []
                    picture_url = images[0].get("src") if images else "NA"
                    item_to_save, created = InventoryModel.objects.update_or_create(user_id=user.user_id, market_item_id=item.get("id"), defaults=dict(title=item.get("name") or "NA", description=json.dumps(item.get("description")) or "NA", category_id=category_id, category=category_name, woo_category_name=category_name, sku=item.get("sku") or 0,  start_price=item.get("price") or 0, price=item.get("price") or 0, picture_detail=picture_url, thumbnailImage="Null", quantity=item.get("stock_quantity") or 0, return_profileID="Null", return_profileName="Null", payment_profileID="Null", payment_profileName="Null", shipping_profileID="Null", shipping_profileName="Null", categoryMappingAllowed="", item_specific_fields="Null", market_logos=json.dumps({"Woocommerce": "https://i.postimg.cc/Wbfbs7QB/woocommerce.png"}), date_created=(item.get("date_created") or "NA").split("T")[0], active=True, vendor_name="Not Found", enable_charity=True, market_name="Woocommerce", map_status=False, fixed_percentage_markup=user.fixed_percentage_markup, fixed_markup=user.fixed_markup, profit_margin=user.profit_margin, min_profit_mergin=user.min_profit_mergin,  market_item_url=item.get("permalink") or "NA"))

                except Exception as e:
                    logger.info(f"Woocommerce Product failed to insert into inventory {e}")



# Function to manually download all items from all marketplace to local inventory
def manually_download_item_from_marketplace_syc_update(userid):
    # Get all marketplace enrollment for the user to sync their products
    user_enrollments = MarketplaceEnronment.objects.filter(user_id=userid) 
    for user in user_enrollments:
        all_ebay_items = []
        # Deal with ebay marketplace
        if user.marketplace_name == "Ebay":
            # Fetch all eBay items by walking backward
            ebay_downloaded_items = get_all_items_on_ebay(enroll_id=user._id)
            if ebay_downloaded_items == None:
                logger.info(f"Ebay inventory download failed with error: {ebay_downloaded_items}")
                continue
            logger.info(f"Ebay inventory download fetched {len(ebay_downloaded_items)} items for user {user.user_id}")
            # Construct a list of ebay items with relevant details
            for item in ebay_downloaded_items:
                all_ebay_items.append({"ebay_item_id":item[0], "ebay_sku":item[1], 'Title':item[2], "ebay_price":item[3], "ebay_quantity":item[4], 'ListingDuration':item[5], 'ListingType':item[6], 'PictureDetails':item[7], 'ShippingProfileID':item[8], 'ShippingProfileName':item[9], 'ReturnProfileID':item[10], 'ReturnProfileName':item[11], 'PaymentProfileID':item[12], 'PaymentProfileName':item[13], 'market_item_url':item[14], 'images':item[15], 'description':item[16]})
            
            # Loop through each item and update or insert into InventoryModel
            for item in all_ebay_items:                         
                try:
                    # If item already exists, skip to next item
                    existing_item = InventoryModel.objects.get(user_id=userid, market_item_id=item.get("ebay_item_id"))
                    description = get_item_full_description(user._id, item.get("ebay_item_id"))
                    InventoryModel.objects.filter(user_id=user.user_id, id=existing_item.id).update(market_item_url=item.get("market_item_url"), description=json.dumps(description))

                except Exception as e:
                    try:
                        # Get product details from eBay
                        product_details = get_item_details(user._id, item.get("ebay_item_id"))
                        description = get_item_full_description(user._id, item.get("ebay_item_id"))
                        if product_details == None:
                            logger.info(f"Ebay get product details failed for item id {item.get('ebay_item_id')} with error: {product_details}")
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
                                
                            inentory, created = InventoryModel.objects.update_or_create(user_id=user.user_id, market_item_id=item.get("ebay_item_id"), defaults={"title": item.get("Title"), "description": json.dumps(description), "location": product_details.get("itemLocation")["country"], "category_id": product_details.get("categoryId"), "category": product_details.get("categoryPath"), "sku": item.get("ebay_sku"), "upc": ebay_upc, "mpn": ebay_mpn, "start_price": product_details.get("price")["value"], "price": product_details.get("price")["value"], "cost": product_details.get("price")["value"], "picture_detail": product_details.get("image")["imageUrl"], "thumbnailImage": product_details.get("additionalImages"), "postal_code": product_details.get("itemLocation")["postalCode"], "city": product_details.get("itemLocation")["city"], "country": product_details.get("itemLocation")["country"], "quantity": item.get("ebay_quantity"), "return_profileID": item.get("ReturnProfileID"), "return_profileName": item.get("ReturnProfileName"), "payment_profileID": item.get("PaymentProfileID"), "payment_profileName": item.get("PaymentProfileName"), "shipping_profileID": item.get("ShippingProfileID"), "shipping_profileName": item.get("ShippingProfileName"), "bestOfferEnabled": True, "listingType": item.get("ListingType"), "item_specific_fields": custom_fields, "market_logos": product_details.get("listingMarketplaceId"), "date_created": product_details.get("itemCreationDate").split("T")[0], "active": True, "vendor_name": "Not Found", "map_status": False, "market_name": "Ebay", "fixed_percentage_markup": user.fixed_percentage_markup, "fixed_markup": user.fixed_markup, "profit_margin": user.profit_margin, "min_profit_mergin": user.min_profit_mergin, "charity_id": user.charity_id, "enable_charity": user.enable_charity, "market_item_url": item.get("market_item_url"), "thumbnailImage": item.get("images")})
                    except Exception as e:
                        logger.info(f"Ebay Product failed to insert into inventory {e}")
                        continue


        elif user.marketplace_name == "Woocommerce":
            # Fetch all item from Woocommerce
            all_woocommerce_items = get_woocommerce_existing_products(userid)
            if all_woocommerce_items ==None:
                logger.info(f"Woocommerce inventory download failed with error: {all_woocommerce_items}")
                continue
            try:
                for item in all_woocommerce_items:
                    # If item already exists, skip to next item
                    existing_item = InventoryModel.objects.get(user_id=userid, market_item_id=item.get("id"))
                    InventoryModel.objects.filter(user_id=userid, id=existing_item.id).update(market_item_url=item.get("permalink"))
            except:
                try:
                    # If item does not exist, insert new item
                    categories = item.get("categories") or []
                    category_id = categories[0]["id"] if categories and "id" in categories[0] else 0
                    category_name = categories[0].get("name") if categories else "NA"
                    images = item.get("images") or []
                    picture_url = images[0].get("src") if images else "NA"
                    item_to_save, created = InventoryModel.objects.update_or_create(user_id=user.user_id, market_item_id=item.get("id"), defaults=dict(title=item.get("name") or "NA", description=json.dumps(item.get("description")) or "NA", category_id=category_id, category=category_name, woo_category_name=category_name, sku=item.get("sku") or 0,  start_price=item.get("price") or 0, price=item.get("price") or 0, picture_detail=picture_url, thumbnailImage="Null", quantity=item.get("stock_quantity") or 0, return_profileID="Null", return_profileName="Null", payment_profileID="Null", payment_profileName="Null", shipping_profileID="Null", shipping_profileName="Null", categoryMappingAllowed="", item_specific_fields="Null", market_logos="Null", date_created=(item.get("date_created") or "NA").split("T")[0], active=True, vendor_name="Not Found", enable_charity=True, market_name="Woocommerce", map_status=False, fixed_percentage_markup=user.fixed_percentage_markup, fixed_markup=user.fixed_markup, profit_margin=user.profit_margin, min_profit_mergin=user.min_profit_mergin,  market_item_url=item.get("permalink") or "NA"))

                except Exception as e:
                    logger.info(f"Woocommerce Product failed to insert into inventory {e}")
                    continue


# Map items in inventory to products vendor update tables
def map_marketplace_items_to_vendor():
    # Get all user in with marketplace enrollment to map their products
    user_token = MarketplaceEnronment.objects.all()
    for user in user_token:
        # Get list of vendors registered by the user
        enrollment = Enrollment.objects.filter(user_id=user.user_id)
        vendor_list = [(vendor.vendor.name.capitalize(), vendor.id) for vendor in enrollment]
        # fetch all items from inventory for the user
        all_marketplace_items = InventoryModel.objects.filter(Q(user_id=user.user_id) & Q(manual_map=False) & Q(map_status=False))
        for item in all_marketplace_items:
            db_items = None
            for vendor_name, enrolled_id in vendor_list:
                try:
                    model_name = vendor_name + "Update"
                    # Get the actual model class from the string name
                    model_class = apps.get_model('vendorEnrollment', model_name)
                    db_items = model_class.objects.filter(Q(enrollment_id=enrolled_id) & Q(sku=item.sku) & (Q(upc=item.upc) | Q(mpn=item.mpn) | (Q(upc__in=[None, ""]) & Q(mpn__in=[None, ""]))))
                    db_items = db_items[0]
                
                    break                    
                except Exception as e:
                    continue
                
            if db_items:
                try:
                    # Check if the product exists in GeneralProduct table
                    try:
                        item_product = Generalproducttable.objects.get(user_id=user.user_id, id=item.product_id)
                    except:
                        item_product = Generalproducttable.objects.create(user_id=user.user_id, sku=db_items.sku, upc=db_items.upc, mpn=db_items.mpn, active=True, total_product_cost=db_items.total_price, map=db_items.map, msrp=db_items.msrp, enrollment_id=db_items.enrollment_id, product_id=db_items.product_id, quantity=db_items.quantity, price=db_items.price, vendor_name=db_items.vendor.name)
                    
                    # Item exists, check if we need to update price or quantity
                    inventory = InventoryModel.objects.filter(market_item_id=item.market_item_id, user_id=user.user_id).update(map_status=True, msrp=db_items.msrp, map=db_items.map, product_id=item_product.id, total_product_cost=db_items.total_price, price=db_items.price, vendor_name=db_items.vendor.name, vendor_identifier=db_items.enrollment.identifier, fixed_percentage_markup=user.fixed_percentage_markup, fixed_markup=user.fixed_markup, profit_margin=user.profit_margin, min_profit_mergin=user.min_profit_mergin)
                    # Update the VendorUpdate table to set listed_market to true
                    db_items.active = True
                    db_items.save()
                    Generalproducttable.objects.filter(user_id=user.user_id, id=item.product_id).update(active=True)
                    # update the product in order table to reflect the mapping
                    OrdersOnEbayModel.objects.filter(marketItemId=item.market_item_id, user_id=user.user_id).update(vendor_name=db_items.vendor.name)
                except Exception as e:
                    logger.info(f"Mapping Product processing failed with error: {e}")
                    continue
     
           