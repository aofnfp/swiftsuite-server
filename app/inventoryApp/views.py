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
from .tasks import check_ebay_item_ended_task, sync_ebay_inventory_task, update_ebay_price_quantity_inventory_task
from woocommerce import API
from decouple import config
from marketplaceApp.views import WooCommerce
from xml.etree.ElementTree import Element, tostring, SubElement
from xml.etree import ElementTree as ET
from vendorEnrollment.utils import with_module
from accounts.permissions import IsOwnerOrHasPermission
from django.db.models import Q
from .utils import query_product_filter
from django.apps import apps


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
        product_info = get_object_or_404(InventoryModel, id=inventory_id)
        serializer = InventoryModelUpdateSerializer(instance=product_info, data=request.data, partial=True)
        if serializer.is_valid():
            if market_name == "Ebay":
                response = mk.update_item_on_ebay(request, userid, inventory_id)
                # Check the response
                if response == "Success":
                    serializer.save()
                    return Response(f"Product updated successfully", status=status.HTTP_200_OK)
                else:
                    return Response(f"Failed to update product on eBay.", status=status.HTTP_400_BAD_REQUEST)

            elif market_name == "Woocommerce":
                response = wooc.update_woocommerce_product(request, userid, market_name, inventory_id)
                if response == "Success":
                    serializer.save()
                    return Response(f"Product updated successfully!", status=status.HTTP_200_OK)
                else:
                    return Response(f"Unexpected error: {response}", status=status.HTTP_400_BAD_REQUEST)
            elif market_name == "Shopify":
                pass
            elif market_name == "Amazon":
                pass
            elif market_name == "all":
                pass
            
        else:
            return Response(f"Form not filled correctly.", status=status.HTTP_400_BAD_REQUEST)
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
            vendor_list = [vendor_name.vendor.name.capitalize() for vendor_name in enrollment]

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
                for prod in product_objects:
                    try:
                        model_name = vendor_name.capitalize() + "Update"
                        # Get the actual model class from the string name
                        model_class = apps.get_model('vendorEnrollment', model_name)
                        conditions = query_product_filter(prod.get("upc"), prod.get("mpn"))
                        db_items = model_class.objects.filter(conditions & Q(sku=prod.get("sku")))
                        if not db_items.exists():
                            prod["error"] = "No matching product found in vendor's inventory"
                            unmapped_items.append(prod)
                            continue
                        
                        db_item = db_items[0]                          
                    except Exception as ea:
                        prod["error"] = str(ea)
                        unmapped_items.append(prod)
                        continue
                    
                    if db_item:
                        try:
                            market_enrollment = MarketplaceEnronment.objects.filter(user_id=userid, market_name=market_name).first()
                            # Modify selling price before updating on ebay 
                            selling_price = float(db_item.total_price) + float(market_enrollment.fixed_markup) + ((float(market_enrollment.fixed_percentage_markup)/100) * float(db_item.total_price)) + ((float(market_enrollment.profit_margin)/100) * float(db_item.total_price))
                            if db_item.map:
                                try:
                                    if selling_price < float(db_item.map):
                                        selling_price = float(db_item.map)
                                except:
                                    return Response(f"Selling price calculation error.", status=status.HTTP_400_BAD_REQUEST)
                            # Create or update the product on GeneralProduct table
                            conditions = query_product_filter(prod.get("upc"), prod.get("mpn"))
                            item_product, created = Generalproducttable.objects.update_or_create(conditions & Q(user_id=user.user_id) & Q(sku=db_item.sku), defaults={"active": True, "total_product_cost": db_item.total_price, "map": db_item.map, "enrollment_id": db_item.enrollment_id, "product_id": db_item.product_id, "quantity": db_item.quantity, "price": db_item.price, "vendor_name": vendor_name})                           
                            # Item exists, check if we need to update price or quantity
                            inentory, created = InventoryModel.objects.update_or_create(id=prod.get("id"), defaults={"map_status": True, "product_id": item_product.id, "total_product_cost": db_item.total_price, "quantity": db_item.quantity, "vendor_name": db_item.vendor.name, "fixed_markup": market_enrollment.fixed_markup, "fixed_percentage_markup": market_enrollment.fixed_percentage_markup, "profit_margin": market_enrollment.profit_margin, "percentage_markup": market_enrollment.percentage_markup})
                            # Update the VendorUpdate table to set listed_market to true
                            db_item.active = True
                            db_item.save()
                            
                        except Exception as e:
                            prod["error"] = str(e)
                            unmapped_items.append(prod)
                            continue
                
                return JsonResponse({"Message": "Items mapped successfully", "Failed to map items":unmapped_items}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to map item.", status=status.HTTP_400_BAD_REQUEST)

    
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
            vendor_list = [vendor_name.vendor.name.capitalize() for vendor_name in enrollment]
            return JsonResponse({"item_details":list(unmapped_item), "vendor_list": list(dict.fromkeys(vendor_list))}, safe=False, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to get items.", status=status.HTTP_400_BAD_REQUEST)

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
            minimum_offer_price = eb.calculated_minimum_offer_price(validated_data['product'].id, validated_data['start_price'], validated_data['min_profit_mergin'], validated_data['profit_margin'], userid)
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
                return "Success"
            else:
                return "Error updating"
        except ConnectionError as e:
            return Response(f"Error in payload", status=status.HTTP_400_BAD_REQUEST)
     
    
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
            
            inventory_listing = InventoryModel.objects.all().filter(user_id=userid, active=True).values().order_by('-date_created','-last_updated')
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
        # eb = Ebay()
        # access_token = eb.refresh_access_token(userid, "Ebay")
        xml_body = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<GetItemResponse xmlns=\"urn:ebay:apis:eBLBaseComponents\"><Timestamp>2025-12-11T15:22:10.389Z</Timestamp><Ack>Success</Ack><Version>1193</Version><Build>E1193_CORE_API_19146280_R1</Build><HardExpirationWarning>2025-12-12 00:22:09</HardExpirationWarning><Item><AutoPay>true</AutoPay><BuyerProtection>ItemIneligible</BuyerProtection><BuyItNowPrice currencyID=\"USD\">0.0</BuyItNowPrice><Charity><CharityName>SoZo Foundation NFP</CharityName><DonationPercent>100.0</DonationPercent><CharityID>188477</CharityID><Mission>SoZo Foundation NFP is a 501 c 3 nonprofit organization founded in Illinos. SoZo Foundation helps less privileged children from developing countries gain access to quality education by donating merchandise such as books, bags, uniforms, and other items that might be found wanting in schools. We build and equip classrooms, libraries, laboratories, computers labs etc. We also plan to build and operate schools to ensure all children have access to quality education needed to help frame their future.</Mission><LogoURL>https://i.ebayimg.com/00/s/MTAyM1gxNjAw/z/LWsAAOSwJahgmY8l/$_1.PNG?set_id=8800005007</LogoURL><Status>Valid</Status></Charity><Country>US</Country><Currency>USD</Currency><Description>&lt;div id=&quot;inkfrog_crosspromo_top&quot;&gt;&lt;/div&gt;\n&lt;!DOCTYPE html PUBLIC &quot;-//W3C//DTD XHTML 1.0 Transitional//EN&quot; &quot;https://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd&quot;&gt;\n&lt;html xmlns=&quot;https://www.w3.org/1999/xhtml&quot;&gt;\n&lt;head&gt;\n&lt;title&gt;JTS Group Dead Center .22 Caliber Semi-Domed Pellets 21.53 Grain 250 Count Tin&lt;/title&gt;\n&lt;meta name=&quot;description&quot; content=&quot;Title&quot;&gt;\n&lt;meta name=&quot;keywords&quot; content=&quot;Title&quot;&gt;\n&lt;link href=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/css/bootstrap.min.css&quot; rel=&quot;stylesheet&quot; type=&quot;text/css&quot;&gt;\n&lt;link href=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/css/listing.css&quot; rel=&quot;stylesheet&quot; type=&quot;text/css&quot;&gt;\n&lt;link href=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/css/reponsive.css&quot; rel=&quot;stylesheet&quot; type=&quot;text/css&quot;&gt;\n&lt;link href=&quot;https://stackpath.bootstrapcdn.com/font-awesome/4.7.0/css/font-awesome.min.css&quot; rel=&quot;stylesheet&quot; integrity=&quot;sha384-wvfXpqpZZVQGK6TAh5PVlGOfQNHSoD2xbE+QkPxCAFlNEevoEH3Sl0sibVcOQVnN&quot; crossorigin=&quot;anonymous&quot;&gt;\n&lt;meta http-equiv=&quot;Content-Type&quot; content=&quot;text/html; charset=utf-8&quot;&gt;\n&lt;meta name=&quot;viewport&quot; content=&quot;width=device-width, initial-scale=1&quot;&gt;\n&lt;style&gt;\nimg {\nmax-width: 100%;\n}\n&lt;/style&gt;\n&lt;link href=&apos;//open.inkfrog.com/templates/designer/styles/user/134645.css&apos; rel=&apos;stylesheet&apos; type=&apos;text/css&apos;&gt;&lt;/head&gt;\n\n&lt;body&gt;\n&lt;div class=&quot;listing_background&quot;&gt; \n&lt;!--Header //start--&gt;\n&lt;div class=&quot;top_bg&quot;&gt;\n&lt;div class=&quot;dezign_wapper&quot;&gt;   \n&lt;div class=&quot;store_header&quot;&gt;\n&lt;div class=&quot;container&quot;&gt;\n&lt;div class=&quot;row align-items-center&quot;&gt;\n&lt;div class=&quot;col-md-4&quot;&gt;\n&lt;div id=&quot;store_logo&quot;&gt;&lt;a href=&quot;https://www.ebay.com/str/sozo&quot; target=&quot;_blank&quot;&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/logo.png&quot; alt=&quot;&quot;&gt;&lt;/a&gt;&lt;/div&gt;\n&lt;/div&gt;\n&lt;div class=&quot;col-md-8&quot;&gt;\n&lt;div class=&quot;top_promo_code&quot;&gt;\n&lt;ul&gt;\n&lt;li class=&quot;left_border&quot;&gt; &lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/top_promo1.png&quot; alt=&quot;&quot;&gt; &lt;/li&gt;\n&lt;li&gt; &lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/top_promo2.png&quot; alt=&quot;&quot;&gt; &lt;/li&gt;\n&lt;/ul&gt;\n&lt;/div&gt; \n&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\n&lt;div class=&quot;store_menu&quot;&gt;\n&lt;div class=&quot;container&quot;&gt;\n&lt;div class=&quot;row&quot;&gt;\n&lt;div class=&quot;col-md-12&quot;&gt;\n&lt;div class=&quot;main_menu&quot;&gt;\n&lt;ul class=&quot;top_main_menu&quot;&gt;\n&lt;li&gt; &lt;a href=&quot;https://www.ebay.com/str/sozo&quot; target=&quot;_blank&quot;&gt;Store Home&lt;/a&gt;&lt;/li&gt;\n&lt;li&gt; &lt;a href=&quot;https://www.ebay.com/sch/i.html?_dmd=2&amp;_dkr=1&amp;iconV2Request=true&amp;_ssn=sozodealz&amp;store_cat=0&amp;store_name=sozo&amp;_oac=1&amp;_sop=10&quot; target=&quot;_blank&quot;&gt;new arrivals&lt;/a&gt;&lt;/li&gt;\t\n&lt;li&gt; &lt;a href=&quot;https://www.ebay.com/sch/sozodealz/m.html?_trksid=p3692&quot; target=&quot;_blank&quot;&gt;Items For Sale &lt;/a&gt;&lt;/li&gt;\n&lt;li&gt; &lt;a href=&quot;https://www.ebay.com/fdbk/feedback_profile/sozodealz?filter=feedback_page%3ARECEIVED_AS_SELLER&quot; target=&quot;_blank&quot;&gt;Feedback&lt;/a&gt;&lt;/li&gt;\n&lt;li&gt; &lt;a href=&quot;https://contact.ebay.com/ws/eBayISAPI.dll?ReturnUserEmail&amp;requested=sozodealz&quot; target=&quot;_blank&quot;&gt;Contact Us&lt;/a&gt;&lt;/li&gt;\n&lt;/ul&gt;\t\n&lt;/div&gt;\n&lt;/div&gt;\t\n&lt;/div&gt;\t\n&lt;/div&gt;\n&lt;/div&gt;    \n&lt;!--Header //end--&gt;\n&lt;div class=&quot;product_section&quot;&gt;\t\n&lt;div class=&quot;container&quot;&gt;\t\t\n&lt;div class=&quot;row&quot;&gt;\n&lt;div class=&quot;col-md-6&quot;&gt;\n&lt;div class=&quot;product_images_wappers&quot;&gt;\n&lt;div class=&quot;product_images_gallery&quot;&gt;&lt;img src=&quot;https://i.frog.ink/ibqO2t26/jtsjac1091hr-1.jpg&quot;&gt;&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\n&lt;div class=&quot;col-md-6&quot;&gt;\n&lt;div class=&quot;listing_listingarea-box&quot; id=&quot;right_box&quot;&gt;\n&lt;div class=&quot;desc-hedtitle&quot;&gt;JTS Group Dead Center .22 Caliber Semi-Domed Pellets 21.53 Grain 250 Count Tin&lt;/div&gt;\n&lt;div class=&quot;desc-rd desc-text&quot;&gt;\n&lt;div vocab=&quot;https://schema.org/&quot; typeof=&quot;Product&quot;&gt;\n&lt;span property=&quot;description&quot;&gt;   \n&lt;p&gt;&lt;p&gt;Upgrade your airgun experience with JTS Group Dead Center .22 Caliber Pellets. Featuring a semi-domed tip design, these pellets combine the aerodynamic benefits of domed pellets with added precision for a range of shooting applications. Each pellet weighs 21.53 grains to ensure consistent and reliable performance. With 250 pellets per tin, they provide excellent value and convenience for target practice, small-game hunting, or plinking. JTS Group, renowned for its innovation and quality, offers these pellets to meet the demands of serious airgun enthusiasts.&lt;/p&gt;&lt;h4&gt;&lt;strong&gt;Key Features&lt;/strong&gt;&lt;/h4&gt;&lt;ul&gt;&lt;li&gt;&lt;strong&gt;Semi-Domed Tip Design&lt;/strong&gt;: Balances aerodynamics and precision for versatile use.&lt;/li&gt;&lt;li&gt;&lt;strong&gt;Precision Weight&lt;/strong&gt;: 21.53 grains for consistent accuracy and reliability.&lt;/li&gt;&lt;li&gt;&lt;strong&gt;Generous Quantity&lt;/strong&gt;: Includes 250 pellets per tin for extended shooting sessions.&lt;/li&gt;&lt;li&gt;&lt;strong&gt;Trusted Brand&lt;/strong&gt;: Manufactured by JTS Group, a leader in airgun accessories.&lt;/li&gt;&lt;/ul&gt;&lt;h4&gt;&lt;strong&gt;Specification&lt;/strong&gt;&lt;/h4&gt;&lt;ul&gt;&lt;li&gt;&lt;strong&gt;Caliber&lt;/strong&gt;: .22&lt;/li&gt;&lt;li&gt;&lt;strong&gt;Pellet Type&lt;/strong&gt;: Semi-Domed Tip&lt;/li&gt;&lt;li&gt;&lt;strong&gt;Weight&lt;/strong&gt;: 21.53 grains&lt;/li&gt;&lt;li&gt;&lt;strong&gt;Quantity&lt;/strong&gt;: 250 pellets per tin&lt;/li&gt;&lt;li&gt;&lt;strong&gt;Model&lt;/strong&gt;: Dead Center&lt;/li&gt;&lt;li&gt;&lt;strong&gt;Brand&lt;/strong&gt;: JTS Group&lt;/li&gt;&lt;/ul&gt;&lt;h4&gt;&lt;strong&gt;Ideal for&lt;/strong&gt;&lt;/h4&gt;&lt;ul&gt;&lt;li&gt;Airgun enthusiasts seeking precise and versatile pellets.&lt;/li&gt;&lt;li&gt;Target shooters aiming for reliable and consistent performance.&lt;/li&gt;&lt;li&gt;Small-game hunters requiring effective and accurate ammunition.&lt;/li&gt;&lt;li&gt;Plinkers and hobbyists needing high-quality airgun pellets.&lt;/li&gt;&lt;/ul&gt;&lt;/p&gt;   \n&lt;/span&gt;\n&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt; \n&lt;/div&gt;\n&lt;/div&gt;   \n&lt;/div&gt;   \n&lt;/div&gt;\n&lt;/div&gt;\t\n&lt;div class=&quot;promotion&quot;&gt;\n&lt;div class=&quot;container&quot;&gt;\n&lt;div class=&quot;row&quot;&gt;\n&lt;div class=&quot;col-md-12&quot;&gt;\n&lt;div class=&quot;promotion_m&quot;&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/promotion.png&quot; alt=&quot;&quot;&gt;&lt;/div&gt;\n&lt;div class=&quot;promotion_res&quot;&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/promotion_res.png&quot; alt=&quot;&quot;&gt;&lt;/div&gt;    \n&lt;/div&gt;   \n&lt;/div&gt;\t\n&lt;/div&gt;\t\n&lt;/div&gt; \t\n&lt;div id=&quot;dezign_home_banner&quot;&gt;\n&lt;div class=&quot;banner_section&quot;&gt;\n&lt;a href=&quot;https://www.ebay.com/str/sozo&quot; target=&quot;_blank&quot;&gt; &lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/banner_01.png&quot; alt=&quot;&quot;&gt; &lt;/a&gt;\n&lt;/div&gt;\n&lt;div class=&quot;banner_section_res&quot;&gt;\n&lt;a href=&quot;https://www.ebay.com/str/sozo&quot; target=&quot;_blank&quot;&gt; &lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/banner_01_res.png&quot; alt=&quot;&quot;&gt; &lt;/a&gt;\n&lt;/div&gt;\t\n&lt;/div&gt; \n&lt;div class=&quot;feature_section&quot;&gt;\n&lt;div class=&quot;feature-title&quot;&gt;  \n&lt;h1&gt;Featured Categories&lt;/h1&gt; \n&lt;p&gt;Browse our latest collection&lt;/p&gt;\t\n&lt;/div&gt;    \n&lt;div class=&quot;container&quot;&gt;\n&lt;div class=&quot;row&quot;&gt;\n&lt;div class=&quot;col-md-4&quot;&gt;\n&lt;div class=&quot;cate_section&quot;&gt;\t\n&lt;div class=&quot;fashion_text&quot;&gt;\n&lt;a href=&quot;https://www.ebay.com/str/sozo/Air-Guns/_i.html?store_cat=36045624016&quot; target=&quot;_blank&quot;&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/cate_01.png&quot; alt=&quot;&quot;&gt;&lt;/a&gt;\t\n&lt;/div&gt;\n&lt;div class=&quot;ring_text&quot;&gt;\n&lt;h1&gt;Air Guns&lt;/h1&gt;\n&lt;/div&gt;\t\n&lt;/div&gt;\n&lt;/div&gt;\t\n&lt;div class=&quot;col-md-4&quot;&gt;\n&lt;div class=&quot;cate_section second_cate&quot;&gt;\t\n&lt;div class=&quot;fashion_text&quot;&gt;\n&lt;a href=&quot;https://www.ebay.com/str/sozo/Camping-Survival/_i.html?store_cat=36045625016&quot; target=&quot;_blank&quot;&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/cate_02.png&quot; alt=&quot;&quot;&gt;&lt;/a&gt;\t\n&lt;/div&gt;\n&lt;div class=&quot;ring_text&quot;&gt;\n&lt;h1&gt;Camping &amp; Survival&lt;/h1&gt;\t\n&lt;/div&gt;\n&lt;/div&gt;\t\t\n&lt;/div&gt;\n&lt;div class=&quot;col-md-4&quot;&gt;\n&lt;div class=&quot;cate_section&quot;&gt;\t\n&lt;div class=&quot;fashion_text&quot;&gt;\n&lt;a href=&quot;https://www.ebay.com/str/sozo/Tactical-and-Duty-Gear/_i.html?store_cat=36838052016&quot; target=&quot;_blank&quot;&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/cate_03.png&quot; alt=&quot;&quot;&gt;&lt;/a&gt;\t\n&lt;/div&gt;\n&lt;div class=&quot;ring_text&quot;&gt;\n&lt;h1&gt;tactical and duty gear&lt;/h1&gt;\n&lt;/div&gt;\n&lt;/div&gt;\t\t\n&lt;/div&gt;     \n&lt;/div&gt;\n&lt;div class=&quot;view_all_btn&quot;&gt;&lt;a href=&quot;https://www.ebay.com/str/sozo&quot; target=&quot;_blank&quot;&gt;Browse All Categories&lt;/a&gt;&lt;/div&gt;    \n&lt;/div&gt;\t\n&lt;/div&gt;\n&lt;div class=&quot;main_who_section&quot;&gt;\n&lt;div class=&quot;container&quot;&gt;\t\n&lt;div class=&quot;about_bg &quot;&gt;\t\t\n&lt;div class=&quot;row align-items-center&quot;&gt;\n&lt;div class=&quot;col-md-7&quot;&gt;\n&lt;div class=&quot;about_text&quot;&gt;\n&lt;div class=&quot;about_img&quot;&gt;Who we are?&lt;/div&gt;\n&lt;h2&gt;About Sozo Outlet&lt;/h2&gt;    \n&lt;p&gt;SoZo is an ecommerce retail brand dedicated to finding the right products at best prices for our customers. We work with distributors around the USA.&lt;/p&gt;\n&lt;h2&gt;Why Buy From US?&lt;/h2&gt;    \n&lt;p&gt;We are a charity owned store and all our net profit goes into ensuring that orphans and vulnerable children in poor cities around the world have access to quality education for a better life. When you buy from us, you are changing lives and helping create a better future where it is mostly needed.&lt;/p&gt;\n&lt;div class=&quot;eBay_msg_t&quot;&gt;&lt;a target=&quot;_blank&quot; href=&quot;https://contact.ebay.com/ws/eBayISAPI.dll?ReturnUserEmail&amp;requested=sozodealz&quot;&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/email_icon.png&quot; alt=&quot;&quot;&gt;eBay Message&lt;/a&gt;&lt;/div&gt;\t\n&lt;/div&gt;\t\t\n&lt;/div&gt;\t\t\n&lt;div class=&quot;col-md-5&quot;&gt;\n&lt;div class=&quot;who_img&quot;&gt;&lt;/div&gt;\t\n&lt;/div&gt;\n&lt;/div&gt;\t\n&lt;/div&gt;\t\n&lt;/div&gt;\t\n&lt;/div&gt; \n&lt;!--Tabs //start--&gt;\n&lt;div class=&quot;main_tab_row&quot;&gt;\n&lt;div class=&quot;tabe_section&quot;&gt; \n&lt;div class=&quot;container&quot;&gt;\n&lt;div class=&quot;row&quot;&gt;\n&lt;div class=&quot;col-md-12&quot;&gt;\n&lt;div class=&quot;main_payment pay_02&quot;&gt;\n&lt;div class=&quot;payment_text&quot;&gt;\n&lt;h1&gt;&lt;span&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/note_icon.png&quot; alt=&quot;&quot;&gt;&lt;/span&gt;Note to Buyers&lt;/h1&gt;\n&lt;/div&gt;\n&lt;div class=&quot;inner_text&quot;&gt;\t\n&lt;p&gt;Due to the nature of the Merchandise, an adult of 21 years or older may be required with a valid ID to sign for all Airgun purchase. Please note that Courier will make 3 attempts for delivery. Courier will not hold this item for pick up at their location or any other location. No pickup option is available for this item. Someone must be available to accept the delivery at the provided address.&lt;/p&gt;\n&lt;h6&gt;Compliance &lt;/h6&gt; \n&lt;p&gt;This listing complies with eBayâs air gun guidelines found here and I will only sell and ship air guns to buyers in jurisdictions where permitted by applicable laws&lt;/p&gt;\n&lt;p&gt;&lt;b&gt;https://pages.ebay.com/help/policies/firearms-weapons-knives.html&lt;/b&gt;&lt;/p&gt;    \n&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\t\n&lt;/div&gt;\t\n&lt;/div&gt;\t\n&lt;/div&gt; \n&lt;div class=&quot;tabe_section&quot;&gt; \n&lt;div class=&quot;container&quot;&gt;\n&lt;div class=&quot;row&quot;&gt;\n&lt;div class=&quot;col-md-12&quot;&gt;\n&lt;div class=&quot;main_payment pay_02&quot;&gt;\n&lt;div class=&quot;payment_text&quot;&gt;\n&lt;h1&gt;&lt;span&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/shiping_icon_01.png&quot; alt=&quot;&quot;&gt;&lt;/span&gt;Shipping Restriction&lt;/h1&gt;\n&lt;/div&gt;\n&lt;div class=&quot;inner_text&quot;&gt;\t\n&lt;h6&gt;Shipping restrictions by location&lt;/h6&gt;    \n&lt;p&gt;It&apos;s up to YOU to know the laws in your state, county and city and to fully comply with them. The following are examples of some state and local restrictions governing various products. This list shows products that are prohibited in the locations indicated. When criteria must be met for ownership, those are also listed.&lt;/p&gt;\n&lt;p&gt;All airsoft guns must have at least a 1/4-inch blaze orange muzzle or an orange flash hider. U.S. federal law requires that all airsoft guns are sold with this marking to avoid the guns being mistaken for firearms. Airguns (guns that shoot pellets or steel BBs) do not have an orange muzzle, nor are they required to have one by the U.S. federal government or any state, county or municipal government ordinance. If you remove the orange muzzle or flash hider from your airsoft gun, you will have voided our 30-day return policy for that item and will not be able to return it for a refund.&lt;/p&gt;\n&lt;p&gt;California&lt;br&gt;\nBlowguns&lt;br&gt;\nBlowgun bolts &amp; darts&lt;br&gt;\nDelaware&lt;br&gt;\nWilmington&lt;/p&gt;  \n&lt;p&gt;Slingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nFlorida&lt;br&gt;\nSt. Augustine&lt;/p&gt;\n&lt;p&gt;Slingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nIllinois&lt;br&gt;\nEffective July 13, 2012: There is no velocity limit on airguns below .18 caliber, and airguns are no longer considered firearms by the state. Airguns over .18 caliber must still have a velocity of less than 700 fps.&lt;br&gt;\nAurora&lt;/p&gt;   \n&lt;p&gt;Foregrips&lt;br&gt;\nChicago&lt;/p&gt;  \n&lt;p&gt;Airguns&lt;br&gt;\nAirsoft guns&lt;br&gt;\nBlank guns&lt;br&gt;\nBlank gun ammo&lt;br&gt;\nCook County&lt;/p&gt; \n&lt;p&gt;Foregrips&lt;br&gt;\nNiles&lt;/p&gt;  \n&lt;p&gt;Slingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nWashington&lt;/p&gt;\n&lt;p&gt;Slingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nIndiana&lt;br&gt;\nSlingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nMassachusetts&lt;br&gt;\nBlowguns&lt;br&gt;\nBlowgun bolts &amp; darts&lt;br&gt;\nSlingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nMichigan&lt;br&gt;\nRichmond&lt;/p&gt;\n&lt;p&gt;Slingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nMinnesota&lt;br&gt;\nDuluth&lt;/p&gt;  \n&lt;p&gt;Slingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nNew Jersey&lt;br&gt;\nSlingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nSilencers, baffles, mufflers or suppressors...internal, removable or non-removable (does not include fake suppressors)\nPellet guns &amp; BB guns: Residents can buy them from us through a designated local gun store after acquiring the appropriate firearm permit (airguns are considered firearms per NJ state law: Title 2C:39-1).&lt;br&gt;\nYour local gun store must fax a copy of their FFL to Air Venturi in order for us to ship the gun you ordered.\n[Airsoft guns may be restricted by some local laws. It is up to you to determine if airsoft guns may be owned/possessed/used without special permits in their locale.]&lt;br&gt;\nNew York&lt;br&gt;\nWrist-braced slingshots&lt;br&gt;\nNew York City &amp; it&apos;s 5 boroughs: Manhattan, Brooklyn, Bronx, Queens &amp; Staten Island&lt;br&gt;\n(incl. ZIP Codes 100xx-104xx, 111xx, 112xx-114xx &amp; 116xx)&lt;/p&gt;\n&lt;p&gt;Airguns&lt;br&gt;\nAirsoft guns&lt;br&gt;\nBB guns&lt;br&gt;\nBlank guns&lt;br&gt;\nBlank gun ammo&lt;br&gt;\nBlowguns&lt;br&gt;\nBlowgun bolts &amp; darts&lt;br&gt;\nCrossbows&lt;br&gt;\nLasers&lt;br&gt;\nLocking folding knives with blades longer than 4 inches&lt;br&gt;\nLongbows&lt;br&gt;\nNorth Carolina&lt;br&gt;\nBlank guns&lt;br&gt;\nBlank gun ammo&lt;br&gt;\nMorehead&lt;/p&gt; \n&lt;p&gt;Slingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nPennsylvania&lt;br&gt;\nPhiladelphia&lt;/p&gt; \n&lt;p&gt;Airguns&lt;br&gt;\nAirsoft guns&lt;br&gt;\nBB guns&lt;br&gt;\nBlowguns&lt;br&gt;\nBlowgun bolts &amp; darts&lt;br&gt;\nCrossbows&lt;br&gt;\nLongbows&lt;br&gt;\nSlingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nPuerto Rico&lt;br&gt;\nBlank guns&lt;br&gt;\nBlank gun ammo&lt;br&gt;\nRhode Island&lt;br&gt;\nBlank guns&lt;br&gt;\nBlank gun ammo&lt;br&gt;\nSlingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nSouth Dakota&lt;br&gt;\nRapid City&lt;/p&gt;\n&lt;p&gt;Slingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nTennessee&lt;br&gt;\nKnoxville&lt;/p&gt; \n&lt;p&gt;Slingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nUtah&lt;br&gt;\nSalt Lake County&lt;/p&gt; \n&lt;p&gt;Slingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nVirginia&lt;br&gt;\nBlank guns&lt;br&gt;\nBlank gun ammo&lt;br&gt;\nFalls Church&lt;/p&gt;\n&lt;p&gt;Slingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nWashington, D.C.&lt;br&gt;\nAirguns&lt;br&gt;\nAirsoft guns&lt;br&gt;\nBB guns&lt;br&gt;\nWest Virginia&lt;br&gt;\nBluefield&lt;/p&gt; \n&lt;p&gt;Slingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;br&gt;\nWisconsin&lt;br&gt;\nMadison&lt;/p&gt;  \n&lt;p&gt;Foregrips&lt;br&gt;\nSlingshots&lt;br&gt;\nSlingshot ammo&lt;br&gt;\nSlingshot accessories&lt;/p&gt;    \n&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\t\n&lt;/div&gt;\t\n&lt;/div&gt;\t\n&lt;/div&gt;    \n&lt;div class=&quot;tabe_section&quot;&gt; \n&lt;div class=&quot;container&quot;&gt;\n&lt;div class=&quot;row&quot;&gt;\n&lt;div class=&quot;col-md-12&quot;&gt;\n&lt;div class=&quot;main_payment pay_02&quot;&gt;\n&lt;div class=&quot;payment_text&quot;&gt;\n&lt;h1&gt;&lt;span&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/payment_icon.png&quot; alt=&quot;&quot;&gt;&lt;/span&gt;Payment&lt;/h1&gt;\n&lt;/div&gt;\n&lt;div class=&quot;inner_text&quot;&gt;\t\n&lt;p&gt;Credit card payments through PayPal and eBay Managed Payments. You can pay with any of the credit cards accepted by PayPal. You don&apos;t even need to have a PayPal account.&lt;/p&gt;    \n&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\t\n&lt;/div&gt;\t\n&lt;/div&gt;\t\n&lt;/div&gt;    \n&lt;div class=&quot;tabe_section&quot;&gt; \n&lt;div class=&quot;container&quot;&gt;\n&lt;div class=&quot;row&quot;&gt;\n&lt;div class=&quot;col-md-12&quot;&gt;\n&lt;div class=&quot;main_payment pay_02&quot;&gt;\n&lt;div class=&quot;payment_text&quot;&gt;\n&lt;h1&gt;&lt;span&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/shiping_icon.png&quot; alt=&quot;&quot;&gt;&lt;/span&gt;Shipping&lt;/h1&gt;\n&lt;/div&gt;\n&lt;div class=&quot;inner_text&quot;&gt;\t\n&lt;p&gt;We always work hard to ensure your package arrives as soon as possible. Please understand that some factors like weather, high postal traffic, and the performance of shipping companies are outside of our control.&lt;/p&gt; \n&lt;p&gt;We offer free shipping to the lower 48 states and ship within 2 - 4 business days of payment, usually sooner. We do not accept P.O. Boxes. Please provide a physical address.&lt;br&gt;We only ship to the address provided at check out. Please verify the address before placing the order.&lt;br&gt;For shipping outside of the continental USA, we only use eBay&apos;s Global Shipping Program. The item is shipped to KY and then sent to the rest of the world. International customers are responsible for all duties and taxes. Continue to check out in order to calculate costs for shipping the item to your country. Messages regarding eBay&apos;s Global Shipping Program MUST be directed at eBay EXCLUSIVELY. Thank you.&lt;/p&gt;    \n&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\t\n&lt;/div&gt;\t\n&lt;/div&gt;\t\n&lt;/div&gt;\n&lt;div class=&quot;tabe_section&quot;&gt;\n&lt;div class=&quot;container&quot;&gt;\n&lt;div class=&quot;row&quot;&gt;\n&lt;div class=&quot;col-md-12&quot;&gt;\n&lt;div class=&quot;main_payment pay_03&quot;&gt;\n&lt;div class=&quot;payment_text&quot;&gt;\n&lt;h1&gt;&lt;span&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/return_icon.png&quot; alt=&quot;&quot;&gt;&lt;/span&gt;Returns&lt;/h1&gt;\n&lt;/div&gt;\n&lt;div class=&quot;inner_text paypal_text&quot;&gt;\n&lt;p&gt;100% Satisfaction Guarantee&lt;/p&gt;\n&lt;p&gt;We will do our best to keep our customers happy. If for any reason you&apos;re not satisfied, please contact us and we&apos;ll help you to resolve any concerns you may have with your purchases and we guarantee you a solution. Please remember We&apos;re Always On Your Side.&lt;/p&gt;\n&lt;p&gt;We&apos;re working very hard to maintain our business reputation and we enjoy providing a world-class service.&lt;/p&gt;\n&lt;p&gt;We gladly accept returns. Please contact us through eBay messaging to request a Return Merchandise Authorization Number (RMA).&lt;/p&gt; \n&lt;p&gt;An RMA must be obtained within 30 days upon received shipment and prior to returning any item.&lt;/p&gt; \n&lt;p&gt;Software, manuals, electronics chart cards are non refundable due to manufacture policies and there is an additional 20% re-stocking fee for unopened package.&lt;/p&gt;\n&lt;p&gt;There will be no restocking fee if an item is returned as a result of our error, shipping errors or merchandise damaged in transit.&lt;/p&gt;\n&lt;p&gt;There is a deduction of 25% on all items that have been opened, 30% on all items that have been used and up to 50% on all items that are not returned in the original packaging.&lt;/p&gt; \n&lt;p&gt;The product must be returned in original condition with all the accessories included.&lt;/p&gt;    \n&lt;/div&gt;\n&lt;/div&gt;\t\n&lt;/div&gt;\t\n&lt;/div&gt;\t\n&lt;/div&gt;\n&lt;/div&gt;     \n&lt;/div&gt;\n&lt;!--Tabs //end--&gt;\n&lt;div class=&quot;guaranteed_wapper&quot;&gt;\n&lt;div class=&quot;container&quot;&gt;\n&lt;div class=&quot;row&quot;&gt;\n&lt;div class=&quot;col-12&quot;&gt;\n&lt;div class=&quot;guaranteed_title&quot;&gt;\n100% Customer Satisfaction Guaranteed &lt;a target=&quot;_blank&quot; href=&quot;https://www.ebay.com/fdbk/feedback_profile/sozodealz?filter=feedback_page%3ARECEIVED_AS_SELLER&quot;&gt;View All Reviews&lt;/a&gt;\n&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\n&lt;div class=&quot;row&quot;&gt;\n&lt;div class=&quot;col-md-3&quot;&gt;\n&lt;div class=&quot;guaranteed_box&quot;&gt;\n&lt;div class=&quot;ebay_logo&quot;&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/ebay_logo.png&quot; alt=&quot;&quot;&gt;&lt;/div&gt;\n&lt;div class=&quot;guaranteed_text&quot;&gt;&quot; As described, arrived on time, great seller &quot;&lt;br&gt;&lt;br&gt;&lt;/div&gt;\n&lt;div class=&quot;guaranteed_name&quot;&gt;Buyer: B***E (125)&lt;/div&gt;\n&lt;div class=&quot;start&quot;&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/start.png&quot; alt=&quot;&quot;&gt;&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\n&lt;div class=&quot;col-md-3&quot;&gt;\n&lt;div class=&quot;guaranteed_box&quot;&gt;\n&lt;div class=&quot;ebay_logo&quot;&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/ebay_logo.png&quot; alt=&quot;&quot;&gt;&lt;/div&gt;\n&lt;div class=&quot;guaranteed_text&quot;&gt;&quot; Item arrived quickly,\nno issues, will trade again\nfor sure &quot;&lt;/div&gt;\n&lt;div class=&quot;guaranteed_name&quot;&gt;Buyer: C***D (private)&lt;/div&gt;\n&lt;div class=&quot;start&quot;&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/start.png&quot; alt=&quot;&quot;&gt;&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\n&lt;div class=&quot;col-md-3&quot;&gt;\n&lt;div class=&quot;guaranteed_box&quot;&gt;\n&lt;div class=&quot;ebay_logo&quot;&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/ebay_logo.png&quot; alt=&quot;&quot;&gt;&lt;/div&gt;\n&lt;div class=&quot;guaranteed_text&quot;&gt;&quot; Happy, good postage\ndeal with anytime &quot;&lt;br&gt;&lt;br&gt;&lt;/div&gt;\n&lt;div class=&quot;guaranteed_name&quot;&gt;Buyer: I***P (69)&lt;/div&gt;\n&lt;div class=&quot;start&quot;&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/start.png&quot; alt=&quot;&quot;&gt;&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\n&lt;div class=&quot;col-md-3&quot;&gt;\n&lt;div class=&quot;guaranteed_box&quot;&gt;\n&lt;div class=&quot;ebay_logo&quot;&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/ebay_logo.png&quot; alt=&quot;&quot;&gt;&lt;/div&gt;\n&lt;div class=&quot;guaranteed_text&quot;&gt;&quot; A hassle free transaction, fast delivery. Would deal with again &quot;&lt;br&gt;&lt;/div&gt;\n&lt;div class=&quot;guaranteed_name&quot;&gt;Buyer: T***R (private)&lt;/div&gt;\n&lt;div class=&quot;start&quot;&gt;&lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/start.png&quot; alt=&quot;&quot;&gt;&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\n&lt;footer&gt;\n&lt;div class=&quot;store_footer_wapper&quot;&gt;\n&lt;div class=&quot;footer_logo&quot;&gt; &lt;a href=&quot;https://www.ebay.com/str/sozo&quot; target=&quot;_blank&quot;&gt; &lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/footer_logo.png&quot; class=&quot;&quot;&gt; &lt;/a&gt; &lt;/div&gt;     \n&lt;div class=&quot;container&quot;&gt;\n&lt;div class=&quot;row align-items-center&quot;&gt;    \n&lt;div class=&quot;col-md-3&quot;&gt;\n&lt;div class=&quot;footer_block footer_block02&quot;&gt;\n&lt;div class=&quot;footer_payment&quot;&gt; &lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/footer_payment.png&quot; class=&quot;img-fluid&quot;&gt; &lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\t\n&lt;div class=&quot;col-md-6&quot;&gt;\n&lt;div class=&quot;footer_block footer_block01&quot;&gt;\n&lt;div class=&quot;footer_menu&quot;&gt;\n&lt;ul&gt;\n&lt;li&gt; &lt;a href=&quot;https://www.ebay.com/str/sozo&quot; target=&quot;_blank&quot;&gt;Store Home&lt;/a&gt; &lt;/li&gt;\n&lt;li&gt; &lt;a href=&quot;https://www.ebay.com/sch/i.html?_dmd=2&amp;_dkr=1&amp;iconV2Request=true&amp;_ssn=sozodealz&amp;store_cat=0&amp;store_name=sozo&amp;_oac=1&amp;_sop=10&quot; target=&quot;_blank&quot;&gt;new arrivals&lt;/a&gt; &lt;/li&gt;    \n&lt;li&gt; &lt;a href=&quot;https://www.ebay.com/sch/sozodealz/m.html?_trksid=p3692&quot; target=&quot;_blank&quot;&gt;Items For Sale&lt;/a&gt; &lt;/li&gt;\t\n&lt;li&gt; &lt;a href=&quot;https://www.ebay.com/fdbk/feedback_profile/sozodealz?filter=feedback_page%3ARECEIVED_AS_SELLER&quot; target=&quot;_blank&quot;&gt;Feedback&lt;/a&gt; &lt;/li&gt;\n&lt;li&gt; &lt;a href=&quot;https://contact.ebay.com/ws/eBayISAPI.dll?ReturnUserEmail&amp;requested=sozodealz&quot; target=&quot;_blank&quot;&gt;Contact Us&lt;/a&gt; &lt;/li&gt;\n&lt;/ul&gt;\n&lt;/div&gt;\n&lt;/div&gt;\t\n&lt;/div&gt;\n&lt;div class=&quot;col-md-3&quot;&gt;\n&lt;div class=&quot;footer_block footer_block03&quot;&gt;\n&lt;div class=&quot;footer_payment&quot;&gt; &lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/shop_confidence.png&quot; class=&quot;img-fluid&quot;&gt; &lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\n&lt;/div&gt;\n&lt;div class=&quot;dezign_copyright&quot;&gt; Â© Copyright 2022, &lt;span&gt;Sozo Outlet. &lt;/span&gt;  All rights reserved. &lt;/div&gt;\n&lt;div class=&quot;dezign_by&quot;&gt; Made with  &lt;img src=&quot;https://dezignbrain.com/ebay/sozo_dealz/listing/images/designby.png&quot;&gt; by &lt;span&gt;eBayshopdesign.org&lt;/span&gt;&lt;/div&gt;    \n&lt;/div&gt;\n&lt;/div&gt;\n&lt;/footer&gt;   \n&lt;/div&gt;\n&lt;/body&gt;\n&lt;/html&gt;\n&lt;div id=&quot;inkfrog_crosspromo_bottom&quot;&gt;&lt;/div&gt;&lt;div id=&quot;inkfrog_credit&quot; style=&apos;margin-bottom:25px;width:100%;text-align:center;&apos;&gt;&lt;div class=&quot;inkfrog_promo&quot; style=&quot;margin-top:40px !important; &quot;&gt;&lt;a href=&apos;https://signin.ebay.com/authorize?client_id=inkFrogI-eBayShop-PRD-45d7504c4-548de517&amp;response_type=code&amp;redirect_uri=inkFrog__Inc.-inkFrogI-eBaySh-vlfzfmcd&amp;scope=https://api.ebay.com/oauth/api_scope https://api.ebay.com/oauth/api_scope/sell.marketing.readonly https://api.ebay.com/oauth/api_scope/sell.marketing https://api.ebay.com/oauth/api_scope/sell.inventory.readonly https://api.ebay.com/oauth/api_scope/sell.inventory https://api.ebay.com/oauth/api_scope/sell.account.readonly https://api.ebay.com/oauth/api_scope/sell.account https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly https://api.ebay.com/oauth/api_scope/sell.fulfillment https://api.ebay.com/oauth/api_scope/sell.analytics.readonly&apos; style=&apos;border:0px;&apos; target=&apos;_blank&apos;&gt;Listing and template services provided by inkFrog&lt;/a&gt;&lt;br&gt;&lt;br&gt;&lt;/div&gt;&lt;a href=&apos;https://signin.ebay.com/authorize?client_id=inkFrogI-eBayShop-PRD-45d7504c4-548de517&amp;response_type=code&amp;redirect_uri=inkFrog__Inc.-inkFrogI-eBaySh-vlfzfmcd&amp;scope=https://api.ebay.com/oauth/api_scope https://api.ebay.com/oauth/api_scope/sell.marketing.readonly https://api.ebay.com/oauth/api_scope/sell.marketing https://api.ebay.com/oauth/api_scope/sell.inventory.readonly https://api.ebay.com/oauth/api_scope/sell.inventory https://api.ebay.com/oauth/api_scope/sell.account.readonly https://api.ebay.com/oauth/api_scope/sell.account https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly https://api.ebay.com/oauth/api_scope/sell.fulfillment https://api.ebay.com/oauth/api_scope/sell.analytics.readonly&apos; style=&apos;border:0px;&apos; target=&apos;_blank&apos;&gt;&lt;img src=&apos;//open.inkfrog.com/assets/img/logos/logo_small.png&apos; style=&apos;border:0px;max-width:100%&apos; alt=&apos;inkFrog&apos;&gt;&lt;/a&gt;&lt;/div&gt;\n&lt;img src=&quot;https://hit.inkfrog.com/t/hit.gif&quot; style=&quot;max-width:100%&quot;&gt;</Description><ItemID>306026850428</ItemID><ListingDetails><Adult>false</Adult><BindingAuction>false</BindingAuction><CheckoutEnabled>true</CheckoutEnabled><ConvertedBuyItNowPrice currencyID=\"USD\">0.0</ConvertedBuyItNowPrice><ConvertedStartPrice currencyID=\"USD\">21.19</ConvertedStartPrice><ConvertedReservePrice currencyID=\"USD\">0.0</ConvertedReservePrice><HasReservePrice>false</HasReservePrice><StartTime>2025-01-08T07:24:58.000Z</StartTime><EndTime>2026-01-08T07:24:58.000Z</EndTime><ViewItemURL>https://www.ebay.com/itm/JTS-Group-Dead-Center-22-Caliber-Semi-Domed-Pellets-21-53-Grain-250-Count-Tin-/306026850428</ViewItemURL><HasUnansweredQuestions>false</HasUnansweredQuestions><HasPublicMessages>false</HasPublicMessages><ViewItemURLForNaturalSearch>https://www.ebay.com/itm/JTS-Group-Dead-Center-22-Caliber-Semi-Domed-Pellets-21-53-Grain-250-Count-Tin-/306026850428</ViewItemURLForNaturalSearch></ListingDetails><ListingDesigner><LayoutID>10000</LayoutID><ThemeID>10</ThemeID></ListingDesigner><ListingDuration>GTC</ListingDuration><ListingType>FixedPriceItem</ListingType><Location>Fort Worth, Texas</Location><PrimaryCategory><CategoryID>178889</CategoryID><CategoryName>Sporting Goods:Outdoor Sports:Air Guns &amp; Slingshots:BBs &amp; Pellets</CategoryName></PrimaryCategory><PrivateListing>false</PrivateListing><ProductListingDetails><UPC>810058881359</UPC><BrandMPN><Brand>JTS Group</Brand><MPN>JAC109</MPN></BrandMPN><IncludeeBayProductDetails>true</IncludeeBayProductDetails></ProductListingDetails><Quantity>23</Quantity><IsItemEMSEligible>false</IsItemEMSEligible><ReservePrice currencyID=\"USD\">0.0</ReservePrice><ReviseStatus><ItemRevised>true</ItemRevised></ReviseStatus><Seller><AboutMePage>false</AboutMePage><Email>abrahamoladotun@gmail.com</Email><FeedbackScore>11138</FeedbackScore><PositiveFeedbackPercent>99.1</PositiveFeedbackPercent><FeedbackPrivate>false</FeedbackPrivate><IDVerified>false</IDVerified><eBayGoodStanding>true</eBayGoodStanding><NewUser>false</NewUser><RegistrationDate>2019-02-10T12:40:38.000Z</RegistrationDate><Site>US</Site><Status>Confirmed</Status><UserID>sozodealz</UserID><UserIDChanged>false</UserIDChanged><UserIDLastChanged>2020-04-25T15:08:13.000Z</UserIDLastChanged><VATStatus>NoVATTax</VATStatus><SellerInfo><AllowPaymentEdit>true</AllowPaymentEdit><CheckoutEnabled>true</CheckoutEnabled><CIPBankAccountStored>false</CIPBankAccountStored><GoodStanding>true</GoodStanding><LiveAuctionAuthorized>false</LiveAuctionAuthorized><MerchandizingPref>OptIn</MerchandizingPref><QualifiesForB2BVAT>false</QualifiesForB2BVAT><StoreOwner>true</StoreOwner><StoreURL>https://www.ebay.com/str/sozodealz</StoreURL><SafePaymentExempt>false</SafePaymentExempt><TopRatedSeller>true</TopRatedSeller></SellerInfo><MotorsDealer>false</MotorsDealer></Seller><SellingStatus><BidCount>0</BidCount><BidIncrement currencyID=\"USD\">0.0</BidIncrement><ConvertedCurrentPrice currencyID=\"USD\">21.19</ConvertedCurrentPrice><CurrentPrice currencyID=\"USD\">21.19</CurrentPrice><HighBidder><AboutMePage>false</AboutMePage><EIASToken>nY+sHZ2PrBmdj6wVnY+sEZ2PrA2dj6MBkIelAJCGowidj6x9nY+seQ==</EIASToken><Email>bailey.clint64@gmail.com</Email><FeedbackScore>39</FeedbackScore><PositiveFeedbackPercent>100.0</PositiveFeedbackPercent><eBayGoodStanding>true</eBayGoodStanding><NewUser>false</NewUser><RegistrationDate>2023-03-09T03:32:20.000Z</RegistrationDate><Site>US</Site><UserID>clibai8379</UserID><VATStatus>NoVATTax</VATStatus><BuyerInfo><ShippingAddress><Country>US</Country><PostalCode>79553-3116</PostalCode></ShippingAddress></BuyerInfo><UserAnonymized>false</UserAnonymized></HighBidder><LeadCount>0</LeadCount><MinimumToBid currencyID=\"USD\">21.19</MinimumToBid><QuantitySold>3</QuantitySold><ReserveMet>true</ReserveMet><SecondChanceEligible>false</SecondChanceEligible><ListingStatus>Active</ListingStatus><QuantitySoldByPickupInStore>0</QuantitySoldByPickupInStore></SellingStatus><ShippingDetails><ApplyShippingDiscount>false</ApplyShippingDiscount><CalculatedShippingRate><WeightMajor measurementSystem=\"English\" unit=\"lbs\">0</WeightMajor><WeightMinor measurementSystem=\"English\" unit=\"oz\">0</WeightMinor></CalculatedShippingRate><SalesTax><SalesTaxPercent>0.0</SalesTaxPercent><ShippingIncludedInTax>false</ShippingIncludedInTax></SalesTax><ShippingServiceOptions><ShippingService>ShippingMethodExpress</ShippingService><ShippingServiceCost currencyID=\"USD\">0.0</ShippingServiceCost><ShippingServiceAdditionalCost currencyID=\"USD\">0.0</ShippingServiceAdditionalCost><ShippingServicePriority>1</ShippingServicePriority><ExpeditedService>false</ExpeditedService><ShippingTimeMin>1</ShippingTimeMin><ShippingTimeMax>3</ShippingTimeMax><FreeShipping>true</FreeShipping></ShippingServiceOptions><ShippingServiceOptions><ShippingService>FedEx2Day</ShippingService><ShippingServiceCost currencyID=\"USD\">35.0</ShippingServiceCost><ShippingServiceAdditionalCost currencyID=\"USD\">0.0</ShippingServiceAdditionalCost><ShippingServicePriority>2</ShippingServicePriority><ExpeditedService>false</ExpeditedService><ShippingTimeMin>1</ShippingTimeMin><ShippingTimeMax>2</ShippingTimeMax></ShippingServiceOptions><ShippingServiceOptions><ShippingService>FedExStandardOvernight</ShippingService><ShippingServiceCost currencyID=\"USD\">45.0</ShippingServiceCost><ShippingServiceAdditionalCost currencyID=\"USD\">0.0</ShippingServiceAdditionalCost><ShippingServicePriority>3</ShippingServicePriority><ExpeditedService>true</ExpeditedService><ShippingTimeMin>1</ShippingTimeMin><ShippingTimeMax>2</ShippingTimeMax></ShippingServiceOptions><ShippingServiceOptions><ShippingService>FedExPriorityOvernight</ShippingService><ShippingServiceCost currencyID=\"USD\">55.0</ShippingServiceCost><ShippingServiceAdditionalCost currencyID=\"USD\">20.0</ShippingServiceAdditionalCost><ShippingServicePriority>4</ShippingServicePriority><ExpeditedService>true</ExpeditedService><ShippingTimeMin>1</ShippingTimeMin><ShippingTimeMax>2</ShippingTimeMax></ShippingServiceOptions><ShippingType>Flat</ShippingType><ThirdPartyCheckout>false</ThirdPartyCheckout><ShippingDiscountProfileID>0</ShippingDiscountProfileID><InternationalShippingDiscountProfileID>0</InternationalShippingDiscountProfileID><ExcludeShipToLocation>US Protectorates</ExcludeShipToLocation><ExcludeShipToLocation>Alaska/Hawaii</ExcludeShipToLocation><ExcludeShipToLocation>APO/FPO</ExcludeShipToLocation><ExcludeShipToLocation>Asia</ExcludeShipToLocation><ExcludeShipToLocation>Middle East</ExcludeShipToLocation><ExcludeShipToLocation>North America</ExcludeShipToLocation><ExcludeShipToLocation>Oceania</ExcludeShipToLocation><ExcludeShipToLocation>Europe</ExcludeShipToLocation><ExcludeShipToLocation>Southeast Asia</ExcludeShipToLocation><ExcludeShipToLocation>Central America and Caribbean</ExcludeShipToLocation><ExcludeShipToLocation>Africa</ExcludeShipToLocation><ExcludeShipToLocation>South America</ExcludeShipToLocation><ExcludeShipToLocation>PO Box</ExcludeShipToLocation><SellerExcludeShipToLocationsPreference>false</SellerExcludeShipToLocationsPreference></ShippingDetails><ShipToLocations>US</ShipToLocations><Site>US</Site><StartPrice currencyID=\"USD\">21.19</StartPrice><Storefront><StoreCategoryID>1</StoreCategoryID><StoreCategory2ID>0</StoreCategory2ID><StoreURL>https://www.ebay.com/str/sozodealz</StoreURL></Storefront><TimeLeft>P27DT16H2M48S</TimeLeft><Title>JTS Group Dead Center .22 Caliber Semi-Domed Pellets 21.53 Grain 250 Count Tin</Title><UUID>5C512C28D0B446039B7659BD1652A77B</UUID><LocationDefaulted>true</LocationDefaulted><GetItFast>false</GetItFast><BuyerResponsibleForShipping>false</BuyerResponsibleForShipping><SKU>JTSJAC109</SKU><PostalCode>76155</PostalCode><PictureDetails><GalleryType>Gallery</GalleryType><PictureURL>https://i.ebayimg.com/00/s/MTYwMFgxNjAw/z/kmIAAOSwsrpnfihG/$_12.JPG?set_id=880000500F</PictureURL><PictureURL>https://i.ebayimg.com/00/s/MTYwMFgxNjAw/z/CUEAAOSwVeFnfihI/$_12.JPG?set_id=880000500F</PictureURL><PictureSource>EPS</PictureSource></PictureDetails><DispatchTimeMax>2</DispatchTimeMax><ProxyItem>false</ProxyItem><BuyerGuaranteePrice currencyID=\"USD\">20000.0</BuyerGuaranteePrice><BuyerRequirementDetails><ShipToRegistrationCountry>true</ShipToRegistrationCountry></BuyerRequirementDetails><IntangibleItem>false</IntangibleItem><ReturnPolicy><RefundOption>MoneyBack</RefundOption><Refund>Money Back</Refund><ReturnsWithinOption>Days_30</ReturnsWithinOption><ReturnsWithin>30 Days</ReturnsWithin><ReturnsAcceptedOption>ReturnsAccepted</ReturnsAcceptedOption><ReturnsAccepted>Returns Accepted</ReturnsAccepted><ShippingCostPaidByOption>Seller</ShippingCostPaidByOption><ShippingCostPaidBy>Seller</ShippingCostPaidBy><InternationalRefundOption>MoneyBack</InternationalRefundOption><InternationalReturnsAcceptedOption>ReturnsAccepted</InternationalReturnsAcceptedOption><InternationalReturnsWithinOption>Days_30</InternationalReturnsWithinOption><InternationalShippingCostPaidByOption>Buyer</InternationalShippingCostPaidByOption></ReturnPolicy><ConditionID>1000</ConditionID><ConditionDisplayName>New</ConditionDisplayName><PostCheckoutExperienceEnabled>false</PostCheckoutExperienceEnabled><SellerProfiles><SellerShippingProfile><ShippingProfileID>192943792019</ShippingProfileID><ShippingProfileName>Default</ShippingProfileName></SellerShippingProfile><SellerReturnProfile><ReturnProfileID>148084438019</ReturnProfileID><ReturnProfileName>Default</ReturnProfileName></SellerReturnProfile><SellerPaymentProfile><PaymentProfileID>148084374019</PaymentProfileID><PaymentProfileName>Default</PaymentProfileName></SellerPaymentProfile></SellerProfiles><ShippingPackageDetails><ShippingIrregular>false</ShippingIrregular><ShippingPackage>PackageThickEnvelope</ShippingPackage><WeightMajor measurementSystem=\"English\" unit=\"lbs\">0</WeightMajor><WeightMinor measurementSystem=\"English\" unit=\"oz\">0</WeightMinor></ShippingPackageDetails><HideFromSearch>false</HideFromSearch><OutOfStockControl>true</OutOfStockControl><eBayPlus>false</eBayPlus><eBayPlusEligible>false</eBayPlusEligible><IsSecureDescription>true</IsSecureDescription></Item></GetItemResponse>"
        try:
            # Namespace used in the XML
            ns = {"eb": "urn:ebay:apis:eBLBaseComponents"}

            root = ET.fromstring(xml_body)

            # Try to find the natural-search URL first
            url_elem = root.find(".//eb:ViewItemURLForNaturalSearch//eb:ViewItemURL", ns)

            # if url_elem is None:
            #     # Fallback: sometimes ViewItemURL is present instead
            #     url_elem = root.find(".//eb:ViewItemURL", ns)

            item_url = url_elem.text if url_elem is not None else None
            return JsonResponse({"Listed_products": item_url}, safe=False, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(f"Failed to fetch data {e}", status=status.HTTP_400_BAD_REQUEST)   
    
    

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
                return "Success"
            elif response.status_code == 404:
                return "Product not found — check the product ID."
            elif response.status_code == 401:
                return "Unauthorized — check your API credentials."
            else:
                return "Unexpected error"
        except ConnectionError as e:
            return Response(f"Error in the form", status=status.HTTP_400_BAD_REQUEST)

    # Get all existing listed product on woocommerce
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_listed_products(request):
        wcm = WooCommerce()
        # Get all products
        products = wcm.wcapi.get("products").json()
        return JsonResponse({"Listed_products":products}, safe=False, status=status.HTTP_200_OK)
    




# Inventory background task invocation
sync_ebay_inventory_task.delay()
update_ebay_price_quantity_inventory_task.delay()
check_ebay_item_ended_task.delay()