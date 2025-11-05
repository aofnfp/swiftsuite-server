import os, requests, json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.csrf import csrf_exempt
from ebaysdk.exception import ConnectionError

from marketplaceApp.models import MarketplaceEnronment
from .models import InventoryModel
from xml.etree import ElementTree as ET
from .serializer import InventoryModelUpdateSerializer
from vendorEnrollment.models import Generalproducttable
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from marketplaceApp.views import Ebay
from .tasks import sync_ebay_inventory_task
from woocommerce import API
from decouple import config
from marketplaceApp.views import WooCommerce



# Function to update product across marketplaces
@api_view(['PUT'])
def update_product_on_marketplace(request, userid, market_name, inventory_id):
    mk = MarketInventory()
    wooc = WooCommerce()
    try:
        product_info = get_object_or_404(InventoryModel, id=inventory_id)
        serializer = InventoryModelUpdateSerializer(instance=product_info, data=request.data, partial=True)
        if serializer.is_valid():
            # get the serializer's data
            validated_data = serializer.validated_data
            # Select the marketplace to list the product
            if market_name == "Ebay":
                response = mk.update_item_on_ebay(userid, validated_data, product_info.item_specific_fields)
                # Check the response
                if response == "success":
                    serializer.save()
                    return Response(f"Update was Successful", status=status.HTTP_200_OK)
                
            elif market_name == "Woocommerce":
                response = wooc.update_woocommerce_product(userid, validated_data, product_info.item_specific_fields, market_name, product_info.market_item_id)
                if response.status_code == 200:
                    serializer.save()
                    return Response(f"Product updated successfully!: {response.json()}", status=status.HTTP_200_OK)
                elif response.status_code == 404:
                    return Response(f"Product not found — check the product ID.:{response.json()}", status=status.HTTP_404_NOT_FOUND)
                elif response.status_code == 401:
                    return Response(f"Unauthorized — check your API credentials.:{response.json()}", status=status.HTTP_401_UNAUTHORIZED)
                else:
                    return Response(f"Unexpected error:{response.json()}", status=status.HTTP_400_BAD_REQUEST)
            elif market_name == "Shopify":
                pass
            elif market_name == "Amazon":
                pass
            elif market_name == "all":
                pass
            
        else:
            return Response(f"Form not filled correctly. {serializer.errors}", status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(f"Error: {e}", status=status.HTTP_400_BAD_REQUEST)

    
# Create your views here.
class MarketInventory(APIView):
    permission_classes = [IsAuthenticated]
    def __init__(self):
        super().__init__()
        # eBay Developer App credentials
        self.client_id = config("EB_CLIENT_ID")
        self.client_secret = config("EB_CLIENT_SECRET")
        self.app_id = config("EB_APP_ID")
        self.cert_id = config("EB_CERT_ID")
        self.dev_id = config("EB_DEV_ID")
        self.ru_name = config("EB_RU_NAME")
        self.ru_name = "https://swiftsuite.app/"
        # eBay API endpoints
        self.authorization_base_url = os.getenv("pro_auth_base_url")
        self.token_url = "https://api.ebay.com/identity/v1/oauth2/token"
        self.inventory_item_url = "https://api.ebay.com/sell/inventory/v1/inventory_item"

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
    def update_item_on_ebay(self, userId, item_specific_fields, validated_data):
        minv = MarketInventory()
        eb = Ebay()
        access_token = eb.refresh_access_token(userId, "Ebay")
        # convert item specific field into xml
        xml_item_specifics = minv.json_to_xml(item_specific_fields)
        # Get the calculated minimum offer price of product going to ebay
        try:
            product_details = Generalproducttable.objects.all().filter(id=validated_data['product'].id, user_id=userId).values()
            enroll_id = product_details[0].get("enrollment_id")
            minimum_offer_price = eb.calculated_minimum_offer_price(enroll_id, validated_data['product'].id, validated_data['start_price'], validated_data['min_profit_mergin'], validated_data['profit_margin'], userId)
            if type(minimum_offer_price) != float:
                return Response(f"Failed to fetch data:", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(f"Failed to fetch data: {e}", status=status.HTTP_400_BAD_REQUEST)

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
            if response.status_code == 200:
                return "success"
            else:
                return Response(f"Error updating:{response}", status=status.HTTP_400_BAD_REQUEST)
        except ConnectionError as e:
            return Response(f"Error in payload:{e}", status=status.HTTP_400_BAD_REQUEST)


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
            return Response(f"Failed to fetch item data.", status=status.HTTP_400_BAD_REQUEST)
            
    
    # Get all product already listed on Ebay from the inventory
    @api_view(['GET'])
    def get_all_inventory_items(request, userid, page_number, num_per_page):
        try:
            inventory_listing = InventoryModel.objects.all().filter(user_id=userid, active=True).values().order_by('id').reverse()
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
            return Response(f"Failed to get items.", status=status.HTTP_400_BAD_REQUEST)
    
    # Get all saved product yet to be listed on Ebay from the inventory
    @api_view(['GET'])
    def get_all_saved_inventory_items(request, userid, page_number, num_per_page):
        try:
            inventory_saved = InventoryModel.objects.all().filter(user_id=userid, active=False).values().order_by('id').reverse()
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
            return Response(f"Failed to get items.", status=status.HTTP_400_BAD_REQUEST)
            
    # Get all unmapped ebay product listing on local table
    @api_view(['GET'])
    def get_unmapped_listing_items(request, userid):
        try:
            unmapped_listing = InventoryModel.objects.all().filter(map_status=False, user_id=userid).values()
            return JsonResponse({"Unmapped_items":list(unmapped_listing)}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get items.", status=status.HTTP_400_BAD_REQUEST)

    # Get saved product in the inventory for listing to ebay
    @api_view(['GET'])
    def get_saved_product_for_listing(request, inventoryid):
        try:
            saved_item = InventoryModel.objects.all().filter(id=inventoryid).values()
            return JsonResponse({"saved_items":list(saved_item)}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get items.", status=status.HTTP_400_BAD_REQUEST)

    # Delete product from inventory
    @api_view(['GET'])
    def delete_product_from_inventory(request, inventoryid):
        try:
            invent_item = InventoryModel.objects.filter(id=inventoryid)
            Generalproducttable.objects.filter(id=invent_item.values()[0].get('product_id')).update(active=False)
            invent_item.delete()
            return Response("Item deleted successfully", status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to delete items.", status=status.HTTP_400_BAD_REQUEST)
    
    # Function to end product listed on ebay and delete from inventory
    @api_view(['GET'])
    def end_delete_product_from_ebay(request, userid, inventoryid):
        eb = Ebay()
        access_token = eb.refresh_access_token(userid, "Ebay")
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
                return Response(f"Error ending item:", status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(f"Failed to delete items.", status=status.HTTP_400_BAD_REQUEST)
    

    # Function to test any api from ebay before implementation
    @api_view(['GET'])
    def function_to_test_api(request):
        """Fetch detailed product information (UPC, EAN, Brand, etc.) using GetItem API."""
        eb = Ebay()
        minv = MarketInventory()
        access_token = eb.refresh_access_token(50,"Ebay")
        
        listings = minv.get_all_items_on_ebay(access_token)
       
        return JsonResponse({"item":listings[0:10], "Total items": len(listings)}, status=status.HTTP_200_OK)



class WooCommerce(APIView):
    # Function to update product on woocommerce store
    def update_woocommerce_product(self, userid, validated_data, item_specific_fields, market_name, market_item_id):
        wooc = WooCommerce()
        try:
            enrollment = MarketplaceEnronment.objects.get(user_id=userid, marketplace_name=market_name)
            # Set up the WooCommerce API client
            wcapi = API(
                url = enrollment.wc_consumer_url, 
                consumer_key = enrollment.wc_consumer_key,  
                consumer_secret = enrollment.wc_consumer_secret, 
                version = "wc/v3"
            )
            # Generate the meta_data values from item specifics
            meta_data = []
            for key, value in json.loads(item_specific_fields).items():
                meta_data.append({"key": key, "value": value})

            # Product payload mapped to WooCommerce
            update_data = {
                "name": validated_data['title'],
                "type": "simple",
                "regular_price": validated_data['start_price'],
                "description": validated_data['description'],
                "sku": validated_data['sku'],
                "stock_quantity": validated_data['quantity'],
                "manage_stock": True,
                "categories": [
                    {"id": wooc.get_category_id(validated_data['woo_category_name'], enrollment.wc_consumer_url, enrollment.wc_consumer_key, enrollment.wc_consumer_secret)}   # Category ID must exist in WooCommerce
                ],
                "images": [
                    {"src": validated_data['picture_detail']}
                ],
                "meta_data": meta_data
            }

            # --- MAKE THE UPDATE REQUEST ---
            response = wcapi.put(f"products/{market_item_id}", update_data)
            return response
        except ConnectionError as e:
            return Response(f"Error:{e}", status=status.HTTP_400_BAD_REQUEST)



    # Get all the products from the WooCommerce store
    @api_view(['GET'])
    def get_all_existing_products(request):
        wcm = WooCommerce()
        products = wcm.wcapi.get("products").json()  
        return JsonResponse({"products": products}, safe=False, status=status.HTTP_200_OK)
    

    @api_view(['GET'])
    def get_listed_products(request):
        wcm = WooCommerce()
        # Get all products
        products = wcm.wcapi.get("products").json()
        return JsonResponse({"Listed_products":products}, safe=False, status=status.HTTP_200_OK)
    




# Inventory background task invocation
sync_ebay_inventory_task.delay()
