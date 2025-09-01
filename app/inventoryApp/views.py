from django.shortcuts import render, redirect
import os, requests, time, json
import base64
from urllib.parse import urlencode, urlparse, parse_qs
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.csrf import csrf_exempt
from ebaysdk.exception import ConnectionError
from .models import InventoryModel
from xml.etree.ElementTree import Element, tostring, SubElement
from xml.etree import ElementTree as ET
from rest_framework import serializers
from marketplaceApp.views import Ebay
from accounts.models import User
from datetime import datetime, timedelta
from ebaysdk.trading import Connection as Trading
from marketplaceApp.models import MarketplaceEnronment
from .serializer import InventoryModelUpdateSerializer
from vendorEnrollment.models import CwrUpdate, FragrancexUpdate, LipseyUpdate, RsrUpdate, SsiUpdate, ZandersUpdate, Generalproducttable
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from ratelimit import limits, sleep_and_retry
from app.inventoryApp.tasks import sync_ebay_inventory_task




# Create your views here.
class MarketInventory(APIView):
    permission_classes = [IsAuthenticated]
    def __init__(self):
        super().__init__()
        # eBay Developer App credentials
        self.client_id = "os.getenv('EBAY_CLIENT_ID')"
        self.client_secret = "os.getenv('EBAY_CLIENT_SECRET')"
        self.app_id = 'os.getenv('EBAY_CLIENT_ID')'
        self.cert_id = 'os.getenv('EBAY_CLIENT_SECRET')'
        self.dev_id = 'os.getenv('EBAY_DEV_ID')'
        self.ru_name = "https://swiftsuite.app/"
        # eBay API endpoints
        self.authorization_base_url = os.getenv("pro_auth_base_url")
        self.token_url = "https://api.ebay.com/identity/v1/oauth2/token"
        self.inventory_item_url = "https://api.ebay.com/sell/inventory/v1/inventory_item"


    
    # Function to refresh the access token using the refresh token
    def refresh_access_token_for_sync(self, userid, market_name):
        eb = Ebay()
        try:
            connection = MarketplaceEnronment.objects.all().get(user_id=userid, marketplace_name=market_name)
        except Exception as e:
            print(f"Failed to fetch access token in inventory: {e}")
            return None
            
        access_token = connection.access_token
        refresh_token = connection.refresh_token

        credentials = f"{eb.client_id}:{eb.client_secret}"
        credentials_base64 = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {credentials_base64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        body = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": " ".join(eb.scopes)  # Ensure scope is passed correctly
        }
            
        response = requests.post(eb.token_url, headers=headers, data=body)
        if response.status_code != 200:
            print(f"Failed to refresh access token. Authorization code has expired: {response.text}")
            return None

        result = response.json()
        access_token = result.get('access_token')
        
        if not access_token:
            print(f"Failed to get access token in inventory from response{result}")
            return None

        MarketplaceEnronment.objects.filter(user_id=userid, marketplace_name=market_name).update(access_token=access_token, refresh_token=refresh_token)
        return access_token
    
    
    
    # Convert a JSON object back to an XML string
    def json_to_xml(self, json_data):
        
        def build_xml_element(parent, data):
            """ Recursively build XML elements from JSON data """
            if isinstance(data, dict):
                for key, value in data.items():
                    # Handle attributes
                    if key == "@attributes":
                        for attr_name, attr_value in value.items():
                            parent.set(attr_name, attr_value)
                    elif key == "#text":
                        parent.text = value
                    else:
                        if isinstance(value, list):  # If multiple elements with the same tag
                            for item in value:
                                child = ET.SubElement(parent, key)
                                build_xml_element(child, item)
                        else:
                            child = ET.SubElement(parent, key)
                            build_xml_element(child, value)
            else:
                parent.text = str(data)
    
        # Load JSON as a dictionary if it's a string
        if isinstance(json_data, str):
            json_data = json.loads(json_data)
    
        # Get the root element name
        root_key = list(json_data.keys())[0]
        root = ET.Element(root_key)
    
        # Build XML recursively
        build_xml_element(root, json_data[root_key])
    
        # Convert to string
        return ET.tostring(root, encoding="unicode")


    # Create a function to update item information on Ebay
    @api_view(['PUT'])
    def update_item_on_ebay(request, inventory_id, userId):
        minv = MarketInventory()
        eb = Ebay()
        access_token = minv.refresh_access_token_for_sync(userId, "Ebay")
        try:
            product_info = get_object_or_404(InventoryModel, id=inventory_id)
            serializer = InventoryModelUpdateSerializer(instance=product_info, data=request.data, partial=True)
            if serializer.is_valid():
                validated_data = serializer.validated_data
        except Exception as e:
            return Response(f"Error: {e}", status=status.HTTP_400_BAD_REQUEST)
        # convert item specific field into xml
        xml_item_specifics = minv.json_to_xml(product_info.item_specific_fields)
        # Get the calculated minimum offer price of product going to ebay
        try:
            product_details = Generalproducttable.objects.all().filter(id=validated_data['product'].id, user_id=userid).values()
            enroll_id = product_details[0].get("enrollment_id")
            minimum_offer_price = eb.calculated_minimum_offer_price(enroll_id, validated_data['product'].id, validated_data['start_price'], validated_data['min_profit_mergin'], validated_data['profit_margin'], userId)
            if type(minimum_offer_price) != float:
                return Response(f"Failed to fetch data:", status=status.HTTP_400_BAD_REQUEST)
        except:
            return Response(f"Failed to fetch data:", status=status.HTTP_400_BAD_REQUEST)
            
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
                    <ItemID>{validated_data['ebay_item_id']}</ItemID>
                    <Title><![CDATA[{validated_data['title']}]]></Title>
                    <Description><![CDATA[
                        {validated_data['description']}
                    ]]></Description>
                    <globalId>EBAY-US</globalId>
                    <PrimaryCategory>
                        <CategoryID>{validated_data['category_id']}</CategoryID>
                    </PrimaryCategory>
                    <ConditionID>1000</ConditionID>
                    <SKU>{validated_data['sku']}</SKU>
                    <ProductListingDetails>
                      <UPC>{validated_data['upc']}</UPC>
                    </ProductListingDetails>
                    <PictureDetails>
                        <PictureURL>{validated_data['picture_detail']}</PictureURL>
                        <!-- ... more PictureURL values allowed here ... -->
                    </PictureDetails>
                    
                    <!-- ... Item specifics are placed here ... -->
                    {xml_item_specifics}
                    
                    <autoPay>false</autoPay>
                    <PostalCode>{validated_data['postal_code']}</PostalCode>
                    <Location>{validated_data['location']}</Location>
                    <Country>US</Country>
                    <Currency>USD</Currency>
                    <ListingDuration>GTC</ListingDuration>
                    <SellerProfiles>
                        <SellerPaymentProfile>
                            <PaymentProfileID>{validated_data['payment_profileID']}</PaymentProfileID>
                        </SellerPaymentProfile>
                        <SellerReturnProfile>
                            <ReturnProfileID>{validated_data['return_profileID']}</ReturnProfileID>
                        </SellerReturnProfile>
                        <SellerShippingProfile>
                            <ShippingProfileID>{validated_data['shipping_profileID']}</ShippingProfileID>
                        </SellerShippingProfile>
                    </SellerProfiles>
                    <StartPrice>{validated_data['start_price']}</StartPrice>
                    <Quantity>{validated_data['quantity']}</Quantity>
                    <ListingDetails>
                      <BestOfferAutoAcceptPrice> {minimum_offer_price} </BestOfferAutoAcceptPrice>
                      <MinimumBestOfferPrice> {minimum_offer_price} </MinimumBestOfferPrice>
                    </ListingDetails>
                    <listingInfo>
                        <bestOfferEnabled>{validated_data['bestOfferEnabled']}</bestOfferEnabled>
                        <buyItNowAvailable>false</buyItNowAvailable>
                        <listingType>{validated_data['listingType']}</listingType>
                        <gift>{validated_data['gift']}</gift>
                        <watchCount>6</watchCount>
                    </listingInfo>
                    <CategoryMappingAllowed>{validated_data['categoryMappingAllowed']}</CategoryMappingAllowed>
                    <IsMultiVariationListing>true</IsMultiVariationListing>
                    <TopRatedListing>false</TopRatedListing>
                </Item>
                </ReviseItemRequest>"""
            # Make the POST request
            response = requests.post(url, headers=headers, data=body)
            # Check the response
            if response.status_code == 200:
                serializer.save()
                return Response(f"Success: {response.text}", status=status.HTTP_200_OK)
            else:
                return Response(f"Error:{response.text}", status=status.HTTP_400_BAD_REQUEST)
        except ConnectionError as e:
            return Response(f"Error:{e}", status=status.HTTP_400_BAD_REQUEST)


    # Get all products already listed on Ebay using sku
    def get_all_items_on_ebay(self, access_token):

        # eBay API endpoint for inventory items
        url = "https://api.ebay.com/sell/inventory/v1/inventory_item/"
        # Set up headers with Authorization using your OAuth access token
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        ebay_items = []
        page_number = 1
        total_pages = 1  # Initialize to 1 to enter the loop
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
    
    # Function to check if ebay item has ended
    def check_if_ebay_item_has_ended(self, item_id, access_token):
        url = f"https://api.ebay.com/buy/browse/v1/item/{item_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
    
        response = requests.get(url, headers=headers)
    
        if response.status_code == 200:
            data = response.json()
            status = data.get("availability", {}).get("pickupOptions", [{}])[0].get("availabilityType", "")
            end_date = data.get("itemEndDate", "")
            title = data.get("title", "Unknown Title")

            if "UNAVAILABLE" in status.upper():
                return Response(f"The item has ended or is no longer available. Ended date was: {end_date}", status=status.HTTP_200_OK)

        else:
            return Response(f"ailed to fetch item data. {response.text}, tatus code: {response.status_code}", status=status.HTTP_400_BAD_REQUEST)
            
    # Function to get details of specific item listing on ebay
    # Limit to 5 calls per second (eBay's typical limit)
    @sleep_and_retry
    @limits(calls=5, period=1)
    def get_item_details(self, access_token, item_id):
        minv = MarketInventory()

        # # Set up the headers with the access token
        # headers = {
        #     'Authorization': f'Bearer {access_token}',
        #     'Content-Type': 'application/json',
        # }
        # # get full product details of the item ordered
        # item_url = f"https://api.ebay.com/buy/browse/v1/item/get_item_by_legacy_id?legacy_item_id={item_id}"
        # response = requests.get(item_url, headers=headers)
        # if response.status_code == 429:  # Rate limit hit
        #     retry_after = int(response.headers.get('Retry-After', 2))
        #     time.sleep(retry_after)
        #     return minv.get_item_details(access_token, item_id)
    
        # product_data = response.json()
        # if response.status_code == 200:
        #     return product_data
        # else:
        #     print(f"Failed to retrieve details for Item ID {item_id}: {response.text}")
        #     return None
            
            
        # """Fetches detailed item information including UPC, EAN, MPN, Brand, etc."""
        # API endpoint and headers
        url = "https://api.ebay.com/ws/api.dll"
        headers = {
            "Content-Type": "text/xml",
            "Authorization": f"Bearer {access_token}",
            "X-EBAY-API-CALL-NAME": "GetItem",
            "X-EBAY-API-VERSION": "967",
            "X-EBAY-API-IAF-TOKEN": access_token
        }
        
        body = f"""<?xml version="1.0" encoding="utf-8"?>
        <GetItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
            <RequesterCredentials>
                <eBayAuthToken>{access_token}</eBayAuthToken>
            </RequesterCredentials>
            <ItemID>{item_id}</ItemID>
            <DetailLevel>ReturnAll</DetailLevel>
        </GetItemRequest>"""
    
        response = requests.post(url, headers=headers, data=body)
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            print(f"item fetched for item_id {item_id}")
            # Extract fields
            title = root.find(".//ebay:Title", namespaces=NAMESPACE).text if root.find(".//ebay:Title", namespaces=NAMESPACE) else "No Title"
            price = root.find(".//ebay:StartPrice", namespaces=NAMESPACE).text if root.find(".//ebay:StartPrice", namespaces=NAMESPACE) else "No Price"
            quantity = root.find(".//ebay:Quantity", namespaces=NAMESPACE).text if root.find(".//ebay:Quantity", namespaces=NAMESPACE) else "0"
            upc = root.find(".//ebay:ItemSpecifics/ebay:NameValueList[ebay:Name='UPC']/ebay:Value", namespaces=NAMESPACE)
            ean = root.find(".//ebay:ItemSpecifics/ebay:NameValueList[ebay:Name='EAN']/ebay:Value", namespaces=NAMESPACE)
            mpn = root.find(".//ebay:ItemSpecifics/ebay:NameValueList[ebay:Name='MPN']/ebay:Value", namespaces=NAMESPACE)
            brand = root.find(".//ebay:ItemSpecifics/ebay:NameValueList[ebay:Name='Brand']/ebay:Value", namespaces=NAMESPACE)
    
            # Convert to text or default to "Not Available"
            upc = upc.text if upc is not None else "Not Available"
            ean = ean.text if ean is not None else "Not Available"
            mpn = mpn.text if mpn is not None else "Not Available"
            brand = brand.text if brand is not None else "Not Available"
            product_details = {"title":title, "price":price, "quantity":quantity, "upc":upc, "ean":ean, "mpn":mpn, "brand":brand}
            print("function is returning product details collected from ebay")
            return product_details

        else:
            print(f"Failed to retrieve details for Item ID {item_id}: {response.text}")
            return None

    # Create a function to update items quantity and price at the background on Ebay
    def update_items_on_ebay(self, access_token, item_id, price, quantity):
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
                    <StartPrice>{price,}</StartPrice>
                    <Quantity>{quantity}</Quantity>
                </Item>
            </ReviseItemRequest>
            """

            # Make the POST request
            response = requests.post(url, headers=headers, data=body)
            # Check the response
            if response.status_code == 200:
                return f"Success: {response.text}"
            else:
                return f"Error:{response.text}"
        except ConnectionError as e:
            return f'Error: {e}'

    # Map items on ebay with the one on local database for updates
    # @api_view(['GET'])
    def sync_ebay_items_with_local():
        eb = Ebay()
        minv = MarketInventory()
        while True:
            # time.sleep(1800)
            print("working to take ebay items for update")
            all_ebay_items = []
            db_item = ""
            user_token = User.objects.all() #get all user to get their access_token
            for user in user_token:
                print("starting in the for loop for inventory")
                access_token = minv.refresh_access_token_for_sync(user.id, "Ebay")
                if not access_token:
                   print(f"Failed to refresh access token. Access token returns none in inventoryapp {user.id}")   
                   continue
                # Fetch all item from eBay
                ebay_items = minv.get_all_items_on_ebay(access_token)
                for item in ebay_items:
                    all_ebay_items.append({"ebay_item_id":item[0], "ebay_sku":item[1], 'Title':item[2], "ebay_price":item[3], "ebay_quantity":item[4], 'ListingDuration':item[5], 'ListingType':item[6], 'PictureDetails':item[7], 'ShippingProfileID':item[8], 'ShippingProfileName':item[9], 'ReturnProfileID':item[10], 'ReturnProfileName':item[11], 'PaymentProfileID':item[12], 'PaymentProfileName':item[13]})
                print("all_ebay_items appended successfully")
                for item in all_ebay_items:
                    inventory_item = InventoryModel.objects.get(sku=item.get("ebay_sku"), user_id=user.id)
                    if inventory_item.vendor_name:
                        # Modify selling price before updating on ebay 
                        print("Trying to calculate selling price and get product for update")
                        selling_price = eb.calculated_selling_price(enroll_id=db_item.enrollment_id, start_price=db_item.total_price, userid=user.id)
                        if db_item.product.map:
                            if selling_price < float(db_item.product.map):
                                selling_price = float(db_item.product.map)
                        print(f"Price calculated successfully for product with id: {item.get('ebay_item_id')}")
                        # Item exists, check if we need to update price or quantity , upc=ebay_upc,
                        InventoryModel.objects.filter(sku=item.get("ebay_sku"), user_id=user.id).update(start_price=selling_price, quantity=db_item.quantity, map_status=True, product_id=db_item.product.id, vendor_name=db_item.vendor.name)
                        print(f"Product updated on inventory table successfully for product with id: {item.get('ebay_item_id')}")
                        # Update the GeneralProduct table to set listed_market to true
                        db_item.active = True
                        db_item.save()
                        print("product updated on inventory successful.")
                        
                        # Check if there is a price and quantity update, then update on Ebay
                        if item["ebay_price"] != selling_price or item["ebay_quantity"] != db_item.quantity:
                            # Update the product on Ebay
                            response = minv.update_items_on_ebay(access_token, item["ebay_item_id"], selling_price, db_item.quantity)
                            print("product updated on ebay successful.")
                    else:
                        product_details = minv.get_item_details(access_token, item.get("ebay_item_id"))
                        if product_details == None:
                            print(f"product details returned None in inventory for item with item_id {item.get('ebay_item_id')}")
                            continue
                        else:
                            # for specific in product_details.get("localizedAspects"):
                                # if specific.get("name") == "UPC":
                                #     ebay_upc = specific.get("value")
                            print(f"product details downloaded successfully")
                        try:
                            # Fetch the item from the local vendor's table
                            vendor_list = ["CwrUpdate", "FragrancexUpdate", "LipseyUpdate", "RsrUpdate", "SsiUpdate", "ZandersUpdate"]
                            for vendor_db in vendor_list:
                                try:
                                    # Get the actual model class from the string name
                                    model_class = globals()[vendor_db]
                                    db_item = model_class.objects.get(sku=item.get("ebay_sku"))   # , upc=ebay_upc , mpn=product_details.get("mpn")
                                    if db_item:
                                        print(f"product product found for vendor: {vendor_db}")
                                        item_listing, created = Generalproducttable.objects.update_or_create(user_id=user.id, sku=db_item.sku, defaults=dict(active=True, upd=product_details.get("upc"), map=db_item.product.map, ))
                                        # Generalproducttable.objects.filter(sku=db_item.sku, user_id=user.id).update(active=True)
                                        print(f"product updated on General product table")
                                        break
                                    else:
                                        print(f"product do not match this vendor")
                                        continue
                                except Exception as ea:
                                    print(f"product do not match any vendor with with sku:{item.get('ebay_sku')} and upc:{product_details.get('upc')} and mpn:{product_details.get('mpn')}: {ea}")
                                    continue
                        except Exception as e:
                            print(f"Attempted operation on this product failed in the first try block {e}")
                            try:
                                # check if item from ebay already inserted before
                                print(f"Trying to check if item is already in the inventory")
                                db_objects = InventoryModel.objects.filter(sku=item.get("ebay_sku"), user_id=user.id)
                                if db_objects:
                                    continue
                                else:
                                    # Item doesn't exist, insert new item
                                    print(f"About to insert into inventory table")
                                    item_to_save = InventoryModel(title=item.get("Title"), description=product_details.get("shortDescription"), location=product_details.get("itemLocation")["country"], category_id=product_details.get("categoryId"), sku=item.get("ebay_sku"), upc=ebay_upc, start_price=product_details.get("price")["value"], picture_detail=product_details.get("image")["imageUrl"],  postal_code=product_details.get("itemLocation")["postalCode"], quantity=item.get("ebay_quantity"), return_profileID=item.get('ReturnProfileID'), return_profileName=item.get('ReturnProfileName'), payment_profileID=item.get('PaymentProfileID'), payment_profileName=item.get('PaymentProfileName'), shipping_profileID=item.get('ShippingProfileID'), shipping_profileName=item.get('ShippingProfileName'), bestOfferEnabled=True, listingType=item.get('ListingType'), gift="", categoryMappingAllowed="", item_specific_fields=product_details.get("localizedAspects"), market_logos=product_details.get("listingMarketplaceId"), ebay_item_id=item.get("ebay_item_id"), user_id=user.id, date_created=product_details.get("itemCreationDate"), active=True, category=product_details.get("categoryPath"), city=product_details.get("itemLocation")["city"], cost=product_details.get("price")["value"], country=product_details.get("itemLocation")["country"], price=product_details.get("price")["value"], thumbnailImage=product_details.get("additionalImages"))
                                    item_to_save.save()
                            except Exception as e:
                                print(f"All attempted operation on this product failed {e}")
                    
    
    # Get all product already listed on Ebay from the inventory
    @api_view(['GET'])
    def get_all_inventory_items(request, userid, page_number, num_per_page):
        try:
            inventory_listing = InventoryModel.objects.all().filter(user_id=userid, active=True).values().order_by('id')
            page = request.GET.get('page', int(page_number))
            paginator = Paginator(inventory_listing, int(num_per_page))
            try:
                inventory_objects = paginator.page(page)
            except PageNotAnInteger:
                inventory_objects = paginator.page(1)
            except EmptyPage:
                inventory_objects = paginator.page(paginator.num_pages)
                
            return JsonResponse({"Total_count":len(inventory_listing), "Total_pages":paginator.num_pages, "Inventory_items":list(inventory_objects)}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get items: {e}", status=status.HTTP_400_BAD_REQUEST)
    
    # Get all saved product yet to be listed on Ebay from the inventory
    @api_view(['GET'])
    def get_all_saved_inventory_items(request, userid, page_number, num_per_page):
        try:
            inventory_saved = InventoryModel.objects.all().filter(user_id=userid, active=False).values().order_by('id')
            page = request.GET.get('page', int(page_number))
            paginator = Paginator(inventory_saved, int(num_per_page))
            try:
                inventory_objects = paginator.page(page)
            except PageNotAnInteger:
                inventory_objects = paginator.page(1)
            except EmptyPage:
                inventory_objects = paginator.page(paginator.num_pages)
            
            return JsonResponse({"Total_count":len(inventory_saved), "Total_pages":paginator.num_pages, "saved_items":list(inventory_objects)}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get items: {e}", status=status.HTTP_400_BAD_REQUEST)
            
    # Get all unmapped ebay product listing on local table
    @api_view(['GET'])
    def get_unmapped_ebay_listing(request, userid):
        try:
            unmapped_listing = InventoryModel.objects.all().filter(map_status=False, user_id=userid).values()
            return JsonResponse({"Unmapped_items":list(unmapped_listing)}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get items: {e}", status=status.HTTP_400_BAD_REQUEST)

    # Get saved product in the inventory for listing to ebay
    @api_view(['GET'])
    def get_saved_product_for_listing(request, inventoryid):
        try:
            saved_item = InventoryModel.objects.all().filter(id=inventoryid).values()
            return JsonResponse({"saved_items":list(saved_item)}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get items: {e}", status=status.HTTP_400_BAD_REQUEST)

    # Delete product from inventory
    @api_view(['GET'])
    def delete_product_from_inventory(request, inventoryid):
        try:
            invent_item = InventoryModel.objects.filter(id=inventoryid)
            Generalproducttable.objects.filter(id=invent_item.values()[0].get('product_id')).update(active=False)
            invent_item.delete()
            return Response("Item deleted successfully", status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to delect items: {e}", status=status.HTTP_400_BAD_REQUEST)
    
    # Function to end product listed on ebay and delete from inventory
    @api_view(['GET'])
    def end_delete_product_from_ebay(request, userid, inventoryid):
        minv = MarketInventory()
        access_token = minv.refresh_access_token_for_sync(userid, "Ebay")
        try:
            invent_item = InventoryModel.objects.filter(id=inventoryid)
            # end item on ebay listing
            url = "https://api.ebay.com/ws/api.dll"
            headers = {
                "X-EBAY-API-CALL-NAME": "EndFixedPriceItem",
                "X-EBAY-API-SITEID": "0",
                "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
                "X-EBAY-API-IAF-TOKEN": access_token,
                "Content-Type": "text/xml"
            }
            body = f"""
            <?xml version="1.0" encoding="utf-8"?>
            <EndFixedPriceItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
                <RequesterCredentials>
                    <eBayAuthToken>{access_token}</eBayAuthToken>
                </RequesterCredentials>
                <ItemID>{invent_item.values()[0].get('ebay_item_id')}</ItemID>
                <EndingReason>NotAvailable</EndingReason>
            </EndFixedPriceItemRequest>
            """
            
            response = requests.post(url, headers=headers, data=body)
            
            # Parse the XML
            namespace = {'ns': 'urn:ebay:apis:eBLBaseComponents'}
            root = ET.fromstring(response.text)
            
            # Extract Ack and ItemID
            ack = root.find('ns:Ack', namespace).text
            
            if response.status_code == 200 and ack == "Success":
                Generalproducttable.objects.filter(id=invent_item.values()[0].get('product_id')).update(active=False)
                invent_item.delete()
                return Response(f"Item ended from ebay successfully {response.text}", status=status.HTTP_200_OK)
            else:
                return Response(f"Error ending item: {response.text}", status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(f"Failed to delect items: {e}", status=status.HTTP_400_BAD_REQUEST)
    
    
    def chunk_skus(self, skus, chunk_size=25):
        for i in range(0, len(skus), chunk_size):
            yield skus[i:i+chunk_size]            
        
    # Function to test any api from ebay before implementation
    @api_view(['GET'])
    def function_to_test_api(request):
        """Fetch detailed product information (UPC, EAN, Brand, etc.) using GetItem API."""
        eb = Ebay()
        minv = MarketInventory()
        sku_list = []
        access_token = eb.refresh_access_token(47, "Ebay")
        
        ebay_items = minv.get_all_items_on_ebay(access_token)
        for item in ebay_items:
            sku_list.append(item[1])

        HEADERS = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        all_results = []
        for batch_num, sku_chunk in enumerate(minv.chunk_skus(sku_list), 1):
            print(f"Processing batch {batch_num} with {len(sku_chunk)} SKUs")
        
            payload = {
                "requests": [{"sku": sku} for sku in sku_chunk]
            }
        
            response = requests.post(
                "https://api.ebay.com/sell/inventory/v1/bulk_get_inventory_item",
                headers=HEADERS,
                json=payload
            )
        
            if response.status_code == 200:
                results = response.json().get("responses", [])
                all_results.extend(results)
            elif response.status_code == 429:
                print("Rate limit hit. Sleeping 30 seconds...")
                time.sleep(30)
                continue
            else:
                print(f"Error {response.status_code}: {response.text}")
                time.sleep(5)
        
            time.sleep(0.5)  # polite delay
        
        return JsonResponse({"saved_items":all_results[0:20]}, safe=False, status=status.HTTP_200_OK)



# run inventory async in background
sync_ebay_inventory_task.delay()
