from datetime import datetime, timedelta
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
from .models import InventoryModel, UpdateLogModel
from xml.etree import ElementTree as ET
from .serializer import InventoryModelUpdateSerializer, MappingToVendorSerializer, SearchQuerySerializer
from vendorEnrollment.models import FragrancexUpdate, Generalproducttable, Enrollment
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from marketplaceApp.views import Ebay
from decouple import config
from marketplaceApp.views import WooCommerce
from xml.etree.ElementTree import Element, tostring, SubElement
from xml.etree import ElementTree as ET
from vendorEnrollment.utils import with_module
from accounts.permissions import IsOwnerOrHasPermission
from django.db.models import Q
from django.apps import apps
from woocommerce import API
from .utils import map_marketplace_items_to_vendor()


# Function to update product across marketplaces
@with_module('inventory')
@permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
@api_view(['PUT'])
def update_product_on_marketplace(request, userid, market_name, inventory_id):
    mk = MarketInventory()
    wooc = WooCommerceInventory()
    # check if user is subaccount
    user = request.user
    if user:
        if user.parent_id:
            userid = user.parent_id

    try:
        if market_name == "Ebay":
            response = mk.update_item_on_ebay(request, userid, inventory_id)
            if response == "Success":
                return Response(f"Product updated successfully", status=status.HTTP_200_OK)
            else:
                return Response(f"Error updating product on Ebay: {response}", status=status.HTTP_400_BAD_REQUEST)

        elif market_name == "Woocommerce":
            response = wooc.update_woocommerce_product(request, userid, market_name, inventory_id)
            if response == "Success":
                return Response(f"Product updated successfully!", status=status.HTTP_200_OK)
            else:
                return Response(f"Error updating product on Woocommerce: {response}", status=status.HTTP_400_BAD_REQUEST)

        elif market_name == "Shopify":
            pass
        elif market_name == "Amazon":
            pass
        elif market_name == "all":
            pass
            
    except Exception as e:
        return Response(f"Error {str(e)}", status=status.HTTP_400_BAD_REQUEST)

# class that takes any other operation not link to any marketplace
class General_operations:
    # Get all unmapped ebay product listing on local table
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_unmapped_listing_items(request, userid, page_number, num_per_page):
        try:
            # check if user is subaccount
            user = request.user
            if user:
                if user.parent_id:
                    userid = user.parent_id
            
            unmapped_item = InventoryModel.objects.all().filter(user_id=userid, map_status=False).values().order_by('id').reverse()
            page = request.GET.get('page', int(page_number))
            paginator = Paginator(unmapped_item, int(num_per_page))
            try:
                inventory_objects = paginator.page(page)
            except PageNotAnInteger:
                inventory_objects = paginator.page(1)
            except EmptyPage:
                inventory_objects = paginator.page(paginator.num_pages)

            enrollment = Enrollment.objects.filter(user_id=userid)
            vendor_list = [vendor.identifier for vendor in enrollment]

            return JsonResponse({"Total_count":len(unmapped_item), "Total_pages":paginator.num_pages, "Inventory_items":list(inventory_objects), "vendor_list": list(dict.fromkeys(vendor_list))}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get items.", status=status.HTTP_400_BAD_REQUEST)


    # Map an item to the right vendor and add to product table
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['PUT'])
    def map_inventory_item_to_vendor(request, userid, market_name):
        try:
            # check if user is subaccount
            user = request.user
            if user:
                if user.parent_id:
                    userid = user.parent_id
            
            serializer = MappingToVendorSerializer(data=request.data)
            if serializer.is_valid():
                serializer_data = serializer.validated_data
                vendor_name = serializer_data['vendor_name']
                product_objects = serializer_data['product_objects']
                unmapped_items = []
                # Get all enrollment details of the user
                enrollment = Enrollment.objects.get(user_id=userid, identifier=vendor_name)
                for prod in product_objects:
                    try:
                        model_name = enrollment.vendor.name.capitalize() + "Update"
                        # Get the actual model class from the string name
                        model_class = apps.get_model('vendorEnrollment', model_name)
                        db_items = model_class.objects.get(((Q(sku=prod.get("sku")) & Q(upc=prod.get("upc"))) | (Q(sku=prod.get("sku")) & Q(mpn=prod.get("mpn")))), enrollment_id=enrollment.id)
                                                 
                    except Exception as ea:
                        prod["error"] = str(ea)
                        unmapped_items.append(prod)
                        continue
                    
                    if db_items:
                        try:
                            market_enrollment = MarketplaceEnronment.objects.filter(user_id=userid, marketplace_name=market_name).first()
                            # Modify selling price before updating on ebay 
                            selling_price = float(db_items.total_price) + float(market_enrollment.fixed_markup) + ((float(market_enrollment.fixed_percentage_markup)/100) * float(db_items.total_price)) + ((float(market_enrollment.profit_margin)/100) * float(db_items.total_price))
                            if db_items.map:
                                try:
                                    if selling_price < float(db_items.map):
                                        selling_price = float(db_items.map)
                                except:
                                    return Response(f"Selling price calculation error.", status=status.HTTP_400_BAD_REQUEST)
                            # Create or update the product on GeneralProduct table
                            item_product, created = Generalproducttable.objects.update_or_create(sku=prod.get("sku"), enrollment_id=enrollment.id, user_id=userid, defaults={"active": True, "total_product_cost": db_items.total_price, "map": db_items.map, "enrollment_id": db_items.enrollment_id, "product_id": db_items.product_id, "quantity": db_items.quantity, "price": db_items.price, "vendor_name": vendor_name})                           
                            # Item exists, check if we need to update price or quantity
                            inentory, created = InventoryModel.objects.update_or_create(id=prod.get("id"), defaults={"map_status": True, "product_id": item_product.id, "total_product_cost": db_items.total_price, "quantity": db_items.quantity, "vendor_name": db_items.vendor.name, "fixed_markup": market_enrollment.fixed_markup, "fixed_percentage_markup": market_enrollment.fixed_percentage_markup, "profit_margin": market_enrollment.profit_margin, "vendor_identifier": vendor_name, "manual_map": True})
                            # Update the VendorUpdate table to set listed_market to true
                            db_items.active = True
                            db_items.save()
                            
                        except Exception as e:
                            prod["error"] = str(e)
                            unmapped_items.append(prod)
                            continue
                
                return JsonResponse({"Message": "Items mapped successfully", "Failed_to_map_items":unmapped_items}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to map item. {e}", status=status.HTTP_400_BAD_REQUEST)

    
    # Get umapped product details in the inventory for mapping to vendor
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_unmapped_product_details(request, userid, inventoryid):
        try:
            # check if user is subaccount
            user = request.user
            if user:
                if user.parent_id:
                    userid = user.parent_id

            unmapped_item = InventoryModel.objects.all().filter(id=inventoryid).values()
            enrollment = Enrollment.objects.filter(user_id=userid)
            vendor_list = [vendor.identifier for vendor in enrollment]
            return JsonResponse({"item_details":list(unmapped_item), "vendor_list": list(dict.fromkeys(vendor_list))}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get items.", status=status.HTTP_400_BAD_REQUEST)

    # Function to get all vendor enrollment for the user
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_all_vendor_enrollment(request, userid):
        try:
            # check if user is subaccount
            user = request.user
            if user:
                if user.parent_id:
                    userid = user.parent_id

            enrollment = Enrollment.objects.filter(user_id=userid)
            vendor_list = [vendor.identifier for vendor in enrollment]
            return JsonResponse({"vendor_list": list(dict.fromkeys(vendor_list))}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get vendor enrollment.", status=status.HTTP_400_BAD_REQUEST)


    # Function to get log update
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_all_log_update(request, userid):
        # check if user is subaccount
        user = request.user
        if user:
            if user.parent_id:
                userid = user.parent_id

        try:
            log_item = UpdateLogModel.objects.all().filter(user_id=userid).values()
            return JsonResponse({"log_items":list(log_item)}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get logs.", status=status.HTTP_400_BAD_REQUEST)


    # Function to get log update
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_log_update_item_details(request, userid, inventoryid):
        # check if user is subaccount
        user = request.user
        if user:
            if user.parent_id:
                userid = user.parent_id

        try:
            log_item_details = InventoryModel.objects.all().filter(user_id=userid, id=inventoryid).values()
            return JsonResponse({"log_items_details":list(log_item_details)}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get logs.", status=status.HTTP_400_BAD_REQUEST)

    
    #  Use search query to filter inventory items
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def search_query_inventory_items(request, userid, page_number, num_per_page):
        try:
            # check if user is subaccount
            user = request.user
            if user:
                if user.parent_id:
                    userid = user.parent_id

            search_query = request.GET.get('search_query', '').strip()
            if not search_query:
                return Response(
                    {"detail": "search_query query parameter is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            inventory_listing = InventoryModel.objects.filter(user_id=userid).filter(
                Q(title__icontains=search_query) |
                Q(sku__icontains=search_query) |
                Q(upc__icontains=search_query) |
                Q(market_item_id__icontains=search_query) |
                Q(vendor_name__icontains=search_query) |
                Q(market_name__icontains=search_query)).values().order_by('id').reverse()
        
            page = request.GET.get('page', int(page_number))
            paginator = Paginator(inventory_listing, int(num_per_page))
            try:
                inventory_objects = paginator.page(page)
            except PageNotAnInteger:
                inventory_objects = paginator.page(1)
            except EmptyPage:
                inventory_objects = paginator.page(paginator.num_pages)
            # Get enrollment details of the user too
            enrollment = MarketplaceEnronment.objects.filter(user_id=userid).values()
            return JsonResponse({"Total_count":inventory_listing.count(), "Total_pages":paginator.num_pages, "Inventory_items":list(inventory_objects), "enrollment_detail":list(enrollment)}, safe=False, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(f"Failed to get items. {e}", status=status.HTTP_400_BAD_REQUEST)

    
#  Use search query to filter unmapped items in the inventory
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def search_query_unmapped_inventory_items(request, userid, page_number, num_per_page):
        try:
            # check if user is subaccount
            user = request.user
            if user:
                if user.parent_id:
                    userid = user.parent_id

            search_query = request.GET.get('search_query', '').strip()
            if not search_query:
                return Response(
                    {"detail": "search_query query parameter is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            inventory_listing = InventoryModel.objects.filter(user_id=userid, map_status=False).filter(
                Q(sku__icontains=search_query) |
                Q(upc__icontains=search_query) |
                Q(market_item_id__icontains=search_query) |
                Q(vendor_name__icontains=search_query) |
                Q(market_name__icontains=search_query)).values().order_by('id').reverse()
        
            page = request.GET.get('page', int(page_number))
            paginator = Paginator(inventory_listing, int(num_per_page))
            try:
                inventory_objects = paginator.page(page)
            except PageNotAnInteger:
                inventory_objects = paginator.page(1)
            except EmptyPage:
                inventory_objects = paginator.page(paginator.num_pages)
            # Get enrollment details of the user too
            enrollment = MarketplaceEnronment.objects.filter(user_id=userid).values()
            return JsonResponse({"Total_count":inventory_listing.count(), "Total_pages":paginator.num_pages, "Inventory_items":list(inventory_objects), "enrollment_detail":list(enrollment)}, safe=False, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(f"Failed to get items. {e}", status=status.HTTP_400_BAD_REQUEST)



    # function to filter get all enrolled marketplace
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_all_marketplaces_enrolled(request, userid):
        try:
            # check if user is subaccount
            user = request.user
            if user:
                if user.parent_id:
                    userid = user.parent_id

            market_enrolled = MarketplaceEnronment.objects.filter(user_id=userid).values_list('marketplace_name', flat=True)
            return JsonResponse({"enrollment_detail":list(market_enrolled)}, safe=False, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(f"Failed to get items. {e}", status=status.HTTP_400_BAD_REQUEST)

# Create your views here.
class MarketInventory:

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
    def update_item_on_ebay(self, request, userid, inventory_id):
        minv = MarketInventory()
        eb = Ebay()
        
        product_info = get_object_or_404(InventoryModel, id=inventory_id)
        serializer = InventoryModelUpdateSerializer(instance=product_info, data=request.data, partial=True)
        if serializer.is_valid():
            # get the serializer's data
            validated_data = serializer.validated_data
        access_token = eb.refresh_access_token(userid, "Ebay")
        # convert item specific field into xml
        xml_item_specifics = minv.json_to_xml(product_info.item_specific_fields)
        # Get the calculated minimum offer price of product going to ebay
        try:
            minimum_offer_price = eb.calculated_minimum_offer_price(validated_data['start_price'], validated_data['min_profit_mergin'], validated_data['profit_margin'])
            if type(minimum_offer_price) != float:
                return Response(f"Failed to fetch data", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(f"Failed to fetch data", status=status.HTTP_400_BAD_REQUEST)

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
            # Validate and format the thumbnail images for listing
            picture_details = Element('PictureDetails')
            SubElement(picture_details, 'PictureURL').text = validated_data['picture_detail']
            if validated_data["thumbnailImage"] != "Null":
                thumbnail_images = validated_data["thumbnailImage"].strip('[]')  # Remove brackets
                thumbnail_images = [url.strip().strip('"') for url in thumbnail_images.split(',')]  # Split and clean URLs
                for img in thumbnail_images:
                    SubElement(picture_details, 'PictureURL').text = img
            # Convert the ElementTree to an XML string
            item_image_url = tostring(picture_details, encoding='unicode')
        except:
            return Response(f"Failed to process thumbnail images:", status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # XML Body for ReviseItem request
            body = f"""
            <?xml version="1.0" encoding="utf-8"?>
            <ReviseItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
                <RequesterCredentials>
                    <eBayAuthToken>{access_token}</eBayAuthToken>
                </RequesterCredentials>
                <Item>
                    <ItemID>{validated_data['market_item_id']}</ItemID>
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
                    {f'''<ProductListingDetails>
                        <UPC>{validated_data['upc']}</UPC>
                    </ProductListingDetails>'''if validated_data['upc']!='Null' else ''}
                    <!-- ... more PictureURL values allowed here ... -->
                    {item_image_url}
                    
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
            # return response
            if response.status_code == 200:
                serializer.save()
                return "Success"
            else:
                return "Error"

        except Exception as e:
            return "Error"
     
    
    # Get all product already listed on Ebay from the inventory
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_all_inventory_items(request, userid, page_number, num_per_page):
        try:
            # check if user is subaccount
            user = request.user
            if user:
                if user.parent_id:
                    userid = user.parent_id
            
            inventory_listing = InventoryModel.objects.all().filter(user_id=userid, active=True).values().order_by('id').reverse()
            page = request.GET.get('page', int(page_number))
            paginator = Paginator(inventory_listing, int(num_per_page))
            try:
                inventory_objects = paginator.page(page)
            except PageNotAnInteger:
                inventory_objects = paginator.page(1)
            except EmptyPage:
                inventory_objects = paginator.page(paginator.num_pages)
            # Get enrollment details of the user too
            enrollment = MarketplaceEnronment.objects.filter(user_id=userid).values()
            return JsonResponse({"Total_count":len(inventory_listing), "Total_pages":paginator.num_pages, "Inventory_items":list(inventory_objects), "enrollment_detail":list(enrollment)}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get items.", status=status.HTTP_400_BAD_REQUEST)
    
    # Get all saved product yet to be listed on Ebay from the inventory
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_all_saved_inventory_items(request, userid, page_number, num_per_page):
        try:
            # check if user is subaccount
            user = request.user
            if user:
                if user.parent_id:
                    userid = user.parent_id
            
            inventory_saved = InventoryModel.objects.all().filter(user_id=userid, active=False).values().order_by('id').reverse()
            page = request.GET.get('page', int(page_number))
            paginator = Paginator(inventory_saved, int(num_per_page))
            try:
                inventory_objects = paginator.page(page)
            except PageNotAnInteger:
                inventory_objects = paginator.page(1)
            except EmptyPage:
                inventory_objects = paginator.page(paginator.num_pages)

             # Get enrollment details of the user too
            enrollment = MarketplaceEnronment.objects.filter(user_id=userid).values()
            return JsonResponse({"Total_count":len(inventory_saved), "Total_pages":paginator.num_pages, "saved_items":list(inventory_objects), "enrollment_detail":list(enrollment)}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get items.", status=status.HTTP_400_BAD_REQUEST)
            

    # Get saved product in the inventory for listing to ebay
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_saved_product_for_listing(request, inventoryid):
        try:
            saved_item = InventoryModel.objects.all().filter(id=inventoryid).values()
            return JsonResponse({"saved_items":list(saved_item)}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get items.", status=status.HTTP_400_BAD_REQUEST)

    # Delete product from inventory
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
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
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def end_delete_product_from_ebay(request, userid, inventoryid):
        eb = Ebay()
        
        # check if user is subaccount
        user = request.user
        if user:
            if user.parent_id:
                userid = user.parent_id
        
        access_token = eb.refresh_access_token(userid, "Ebay")
        try:
            invent_item = InventoryModel.objects.get(id=inventoryid)
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
                <ItemID>{invent_item.market_item_id}</ItemID>
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
                Generalproducttable.objects.filter(id=invent_item.product_id).update(active=False)
                invent_item.delete()
                return Response(f"Item ended from ebay successfully {response.text}", status=status.HTTP_200_OK)
            else:
                return Response(f"Error ending item:", status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(f"Failed to delete items.", status=status.HTTP_400_BAD_REQUEST)
    

    # Function to test any api from ebay before implementation
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def function_to_test_api(request, userid, item_id):
        # check if user is subaccount
        user = request.user
        if user:
            if user.parent_id:
                userid = user.parent_id
        eb = Ebay()
        access_token = eb.refresh_access_token(userid, "Ebay")
    
        # Set eBay API endpoint and headers
        try:
            HEADERS = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
                }   
            all_orders = []
            base_url = "https://api.ebay.com/sell/fulfillment/v1/order"
            limit = 100
            offset = 0

            # Custom date range
            start_time = (datetime.utcnow() - timedelta(days=7)).isoformat(timespec="seconds") + "Z"
            params = {
                "filter": f"creationdate:[{start_time}..]",
                "limit": limit
            }

            while True:
                params["offset"] = offset
                response = requests.get(base_url, headers=HEADERS, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if "orders" not in data:
                        break
                    orders = data["orders"]
                    all_orders.extend(orders)
                    if len(orders) < limit:
                        break
                    offset += limit
                else:
                    if response.json().get('errors')[0]['errorId'] == 1001:
                        return None
                    else:
                        return "Error"
            return JsonResponse({"ordered_items":all_orders}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get items.", status=status.HTTP_400_BAD_REQUEST)

        
   
    

class WooCommerceInventory:
    # Function to update product on woocommerce store
    def update_woocommerce_product(self, request, userid, market_name, inventory_id):
        wooc = WooCommerce()
        try:
            # check if user is subaccount
            user = request.user
            if user:
                if user.parent_id:
                    userid = user.parent_id
                
            enrollment = MarketplaceEnronment.objects.get(user_id=userid, marketplace_name=market_name)
            # Set up the WooCommerce API client
            wcapi = API(
                url = enrollment.wc_consumer_url, 
                consumer_key = enrollment.wc_consumer_key,  
                consumer_secret = enrollment.wc_consumer_secret, 
                version = "wc/v3"
            )
            product_info = get_object_or_404(InventoryModel, id=inventory_id)
            serializer = InventoryModelUpdateSerializer(instance=product_info, data=request.data, partial=True)
            if serializer.is_valid():
                # get the serializer's data
                validated_data = serializer.validated_data
            # Generate the meta_data values from item specifics
            meta_data = []
            for key, value in json.loads(product_info.item_specific_fields).items():
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
            response = wcapi.put(f"products/{product_info.market_item_id}", update_data)
            if response.status_code == 200:
                serializer.save()
                return "Success"
            elif response.status_code == 404:
                return "Product not found — check the product ID."
            elif response.status_code == 401:
                return "Unauthorized — check your API credentials."
            else:
                return "Unexpected error"
        except ConnectionError as e:
            return "Error"

    # Get all existing listed product on woocommerce
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_listed_products(request):
        wcm = WooCommerce()
        # Get all products
        products = wcm.wcapi.get("products").json()
        return JsonResponse({"Listed_products":products}, safe=False, status=status.HTTP_200_OK)
    


map_marketplace_items_to_vendor()