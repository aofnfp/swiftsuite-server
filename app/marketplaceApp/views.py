from django.shortcuts import render, redirect, get_object_or_404
import webbrowser
import requests
import base64
import os, json, random
from urllib.parse import urlencode, urlparse, parse_qs
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from .serializers import MarketplaceEnrolSerializer, GetAuthCodeSerializer, ItemListingToEbaySerializer, UploadedProductImageSerializer, WooComerceEnrolSerializer
from rest_framework.decorators import api_view, parser_classes, permission_classes
from .models import MarketplaceEnronment, UploadedProductImage
from inventoryApp.models import InventoryModel
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.views.decorators.csrf import csrf_exempt
from ebaysdk.exception import ConnectionError
from vendorActivities.models import Vendors
from vendorEnrollment.models import Generalproducttable, Enrollment
from xml.etree.ElementTree import Element, tostring, SubElement
from xml.etree import ElementTree as ET
from rest_framework import serializers
from ebaysdk.trading import Connection as Trading
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from woocommerce import API
from decouple import config
from rest_framework.parsers import MultiPartParser, FormParser


# Function to list product on marketplace
@api_view(['POST'])
def listing_on_marketplace(request, userid, market_name, category_id_or_name):
    eb = Ebay()
    wooc = WooCommerce()
    access_token = eb.refresh_access_token(userid, market_name)
    if not access_token:
        return Response(f"Failed to refresh access token. Get authorization code first", status=status.HTTP_400_BAD_REQUEST)   
    # Fetch item specifics from eBay using the leaf category ID and generate the serializer
    item_specifics_data = eb.get_item_specifics_from_ebay(access_token, int(category_id_or_name))
    if not item_specifics_data:
        return Response({"error": "Failed to fetch item specifics from eBay."}, status=status.HTTP_400_BAD_REQUEST)
    
    item_specifics = item_specifics_data.get('aspects', [])
    # Generate the dynamic serializer by combining eBay fields and model fields (Product model)
    DynamicItemSpecificsSerializer, item_specifics_fields, valid_choices_fields = ItemListingToEbaySerializer.generate_item_specifics_serializer(item_specifics)
    # Pass request data to the dynamic serializer for validation
    serializer = DynamicItemSpecificsSerializer(data=request.data)      
    if serializer.is_valid():
        validated_data = serializer.validated_data
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  
        
    # Get the calculated price of the product to list
    try:
        product_details = Generalproducttable.objects.all().filter(id=validated_data['product'].id, user_id=userid).values()
        enroll_id = product_details[0].get("enrollment_id")
        minimum_offer_price = eb.calculated_minimum_offer_price(enroll_id, validated_data['product'].id, validated_data['start_price'], validated_data['min_profit_mergin'], validated_data['profit_margin'], userid)
        if type(minimum_offer_price) != float:
            return Response(f"Failed to fetch data: minimum offer price error.", status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(f"Failed to fetch data: {e}", status=status.HTTP_400_BAD_REQUEST)
    
    # Select the marketplace to list the product
    if market_name == "Ebay":
        return eb.product_listing_to_ebay(userid, access_token, item_specifics_fields, validated_data, minimum_offer_price)
    elif market_name == "Woocommerce":
        return wooc.list_product_on_woocommerce(request, userid, market_name, category_id_or_name, validated_data)
    elif market_name == "Shopify":
        pass
    elif market_name == "Amazon":
        pass
    elif market_name == "all":
        eb.product_listing_to_ebay(request, userid, market_name, int(category_id_or_name))
        wooc.list_product_on_woocommerce(request, userid, market_name, category_id_or_name)

# Function to save product before listing on marketplace
@api_view(['POST'])
def save_product_before_listing_on_marketplace(request, market_name, userid, category_id_or_name):
    eb = Ebay()
    wooc = WooCommerce()

    access_token = eb.refresh_access_token(userid, market_name)
    if not access_token:
        return Response(f"Failed to refresh access token. Get authorization code first", status=status.HTTP_400_BAD_REQUEST)   
    # Fetch item specifics from eBay and generate the serializer
    item_specifics_data = eb.get_item_specifics_from_ebay(access_token, category_id_or_name)
    if not item_specifics_data:
        return Response({"error": "Failed to fetch item specifics from eBay."}, status=status.HTTP_400_BAD_REQUEST)
        
    item_specifics = item_specifics_data.get('aspects', [])
    # Generate the dynamic serializer by combining eBay fields and model fields (Product model)
    DynamicItemSpecificsSerializer, item_specifics_fields, valid_choices_fields = ItemListingToEbaySerializer.generate_item_specifics_serializer(item_specifics)
    # Pass request data to the dynamic serializer for validation
    serializer = DynamicItemSpecificsSerializer(data=request.data)      
    if serializer.is_valid():
        validated_data = serializer.validated_data
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  
    
    # Select the marketplace to list the product
    if market_name == "Ebay":
        return eb.product_listing_to_ebay(userid, item_specifics_fields, validated_data)
    elif market_name == "Woocommerce":
        return wooc.list_product_on_woocommerce(request, userid, market_name, category_id_or_name, validated_data)
    elif market_name == "Shopify":
        pass
    elif market_name == "Amazon":
        pass
    elif market_name == "all":
        eb.product_listing_to_ebay(request, userid, market_name, int(category_id_or_name))
        wooc.list_product_on_woocommerce(request, userid, market_name, category_id_or_name)




class Ebay(APIView):
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
        # eBay API endpoints
        self.authorization_base_url = "https://signin.ebay.com/authorize"
        self.token_url = "https://api.ebay.com/identity/v1/oauth2/token"
        self.fulfillment_policy_url = "https://api.ebay.com/sell/account/v1/fulfillment_policy"
        self.payment_policy_url = "https://api.ebay.com/sell/account/v1/payment_policy"
        self.return_policy_url = "https://api.ebay.com/sell/account/v1/return_policy"
        
        self.listing_item_url = "https://api.ebay.com/sell/inventory/v1/inventory_item"

        # eBay API scopes
        self.scopes = [
            "https://api.ebay.com/oauth/api_scope",
            "https://api.ebay.com/oauth/api_scope/sell.marketing.readonly",
            "https://api.ebay.com/oauth/api_scope/sell.marketing",
            "https://api.ebay.com/oauth/api_scope/sell.inventory.readonly",
            "https://api.ebay.com/oauth/api_scope/sell.inventory",
            "https://api.ebay.com/oauth/api_scope/sell.account.readonly",
            "https://api.ebay.com/oauth/api_scope/sell.account",
            "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly",
            "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
            "https://api.ebay.com/oauth/api_scope/sell.analytics.readonly",
            "https://api.ebay.com/oauth/api_scope/sell.finances",
            "https://api.ebay.com/oauth/api_scope/sell.payment.dispute",
            "https://api.ebay.com/oauth/api_scope/commerce.identity.readonly",
            "https://api.ebay.com/oauth/api_scope/sell.reputation",
            "https://api.ebay.com/oauth/api_scope/sell.reputation.readonly",
            "https://api.ebay.com/oauth/api_scope/commerce.notification.subscription",
            "https://api.ebay.com/oauth/api_scope/commerce.notification.subscription.readonly",
            "https://api.ebay.com/oauth/api_scope/sell.stores",
            "https://api.ebay.com/oauth/api_scope/sell.stores.readonly"
        ]

    # Function to get access_token and refresh_token if connection is established or re-establish connection to get access_token if expires.
   
    def make_connection_to_get_auth_code(request, market_name):
        eb = Ebay()
        
        # Construct the authorization URL
        authorization_params = {
            "client_id": eb.client_id,
            "redirect_uri": eb.ru_name,
            "response_type": "code",
            "scope": " ".join(eb.scopes)
        }
        authorization_url = eb.authorization_base_url + '?' + urlencode(authorization_params)

        # Open the authorization URL in the default browser
        # webbrowser.open(authorization_url)
        return redirect(authorization_url)

        # Redirect the user to the authorization URL
        # return JsonResponse({"message": "Please complete the authorization in your browser."})

    @api_view(['POST'])
    def oauth_callback(request, userid, market_name):
        eb = Ebay()
        # Validate the code using the serializer
        serializer = GetAuthCodeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        parsed_url = urlparse(serializer.validated_data["authorization_code"])
        query_params = parse_qs(parsed_url.query)
        authorization_code = query_params.get('code', [None])[0]

        if not authorization_code:
            return Response("Authorization code not found.", status=status.HTTP_400_BAD_REQUEST)
        
        access_token, refresh_token = eb.get_access_token(authorization_code, userid, market_name)
        return JsonResponse({"Authorization": "Connection was successful"}, safe=False, status=200)


    def get_access_token(request, authorization_code, userid, market_name):
        eb = Ebay()
        credentials = f"{eb.client_id}:{eb.client_secret}"
        credentials_base64 = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {credentials_base64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        body = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": eb.ru_name
        }

        try:
            response = requests.post(eb.token_url, headers=headers, data=body)
            if response.status_code != 200:
                return Response(f"Failed to obtain access token: {response.text}", status=status.HTTP_400_BAD_REQUEST)
            
            result = response.json()
            access_token = result.get('access_token')
            refresh_token = result.get('refresh_token')
            
            if not access_token:
                return Response(f"Failed to obtain access token from response: {result}", status=status.HTTP_400_BAD_REQUEST)
        except:
            return Response(f"Failed to obtain access token: {response.text}", status=status.HTTP_400_BAD_REQUEST)
        
        obj, created = MarketplaceEnronment.objects.update_or_create(user_id=userid, marketplace_name=market_name, defaults={"access_token":access_token, "refresh_token":refresh_token})  
        return access_token, refresh_token

    # Function to refresh the access token using the refresh token
    def refresh_access_token(request, userid, market_name):
        eb = Ebay()
        try:
            connection = MarketplaceEnronment.objects.all().get(user_id=userid, marketplace_name=market_name)
        except Exception as e:
            return Response(f"Failed to fetch access token: {e}", status=status.HTTP_400_BAD_REQUEST)
        
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
            return Response(f"Failed to refresh access token. Authorization code has expired: {response.text}", status=status.HTTP_400_BAD_REQUEST)

        result = response.json()
        access_token = result.get('access_token')
        
        if not access_token:
            return Response(f"Failed to get access token from response{result}", status=status.HTTP_400_BAD_REQUEST)

        MarketplaceEnronment.objects.filter(user_id=userid, marketplace_name=market_name).update(access_token=access_token, refresh_token=refresh_token)
        return access_token

    # Function to fetch fulfillment policies using the access token
    def fetch_fulfillment_policies(self, access_token, marketplace_id):
        eb = Ebay()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        params = {
            "marketplace_id": marketplace_id
        }
        response = requests.get(eb.fulfillment_policy_url, headers=headers, params=params)
        if response.status_code == 401:
            return JsonResponse({"Message":"Access token is invalid. Refreshing access token."}, status=status.HTTP_401_UNAUTHORIZED)
        elif response.status_code != 200:
            return JsonResponse({"Message":f"Failed to fetch fulfillment policies: {response.text}"}, status=status.HTTP_400_BAD_REQUEST)
        
        return response.json()

    # Function to fetch payment policies using the access token
    def fetch_payment_policies(self, access_token, marketplace_id):
        eb = Ebay()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        params = {
            "marketplace_id": marketplace_id
        }

        response = requests.get(eb.payment_policy_url, headers=headers, params=params)
        if response.status_code == 401:
            return JsonResponse({"Message":"Access token is invalid. Refreshing access token."}, status=status.HTTP_401_UNAUTHORIZED)
        elif response.status_code != 200:
            return JsonResponse({"Message":f"Failed to fetch payment policies: {response.text}"}, status=status.HTTP_400_BAD_REQUEST)

        return response.json()

    # Function to fetch shipping policies using the access token
    def fetch_return_policies(self, access_token, marketplace_id):
        eb = Ebay()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        params = {
            "marketplace_id": marketplace_id
        }

        response = requests.get(eb.return_policy_url, headers=headers, params=params)
        if response.status_code == 401:
            return JsonResponse({"Mesage":f"Access token is invalid. Refreshing access token. {response.text}"}, status=status.HTTP_401_UNAUTHORIZED)
        elif response.status_code != 200:
            return JsonResponse({"Message":f"Failed to fetch shipping policies: {response.text}"}, status=status.HTTP_400_BAD_REQUEST)
        
        return response.json()
    
       
    # Get user's Ebay account store ID from Ebay
    def get_ebay_user_id(self, access_token):
        # API Endpoint
        url = "https://api.ebay.com/ws/api.dll"
        
        # Set the headers
        headers = {
            "X-EBAY-API-CALL-NAME": "GetStore",
            "X-EBAY-API-SITEID": "0",
            "X-EBAY-API-COMPATIBILITY-LEVEL": "1235",
            "X-EBAY-API-IAF-TOKEN": access_token,
            "X-EBAY-API-REQUEST-ENCODING": "XML",
            "Content-Type": "text/xml"
        }
        
        # XML Payload for GetStore request
        body = f"""<?xml version="1.0" encoding="utf-8"?>
        <GetStoreRequest xmlns="urn:ebay:apis:eBLBaseComponents">
            <RequesterCredentials>
                <eBayAuthToken>{access_token}</eBayAuthToken>
            </RequesterCredentials>
        </GetStoreRequest>
        """
        
        # Make the request
        response = requests.post(url, headers=headers, data=body)
        
        # Check the response
        if response.status_code == 200:# Parse the XML
            namespace = {"ebay": "urn:ebay:apis:eBLBaseComponents"}
            root = ET.fromstring(response.text)
            
            # Extract URLPath (store ID) and Logo URL
            url_path = root.find(".//ebay:URLPath", namespace)
            logo_url = root.find(".//ebay:Logo/ebay:URL", namespace)
            
            # Construct the dictionary
            store_info = {
                "store_id": url_path.text if url_path is not None else None,
                "store_logo": logo_url.text if logo_url is not None else None
            }

            return store_info
        else:
            return Response(f"Error: {response.status_code} - {response.text}")
            

    # Create a function to collect all the required policies from Ebay.
    @api_view(['GET'])
    def refresh_connection_and_get_policy(request, userid, market_name):
        eb = Ebay()
        marketplace_id = "EBAY_US"
        all_policy = {}
        access_token = eb.refresh_access_token(userid, market_name)
        if not access_token:
            return Response(f"Failed to refresh access token. Get authorization code first", status=status.HTTP_400_BAD_REQUEST) 
 
        # Fetch fulfillment policies
        fulfillment_policies = eb.fetch_fulfillment_policies(access_token, marketplace_id)
        if type(fulfillment_policies) != dict:
            return Response(f"Failed to refresh access token. Get authorization code first", status=status.HTTP_400_BAD_REQUEST)
        all_policy.update(fulfillment_policies=fulfillment_policies)
        
        # Fetch payment policies
        payment_policies = eb.fetch_payment_policies(access_token, marketplace_id)
        if type(payment_policies) != dict:
            return Response(f"Failed to refresh access token. Get authorization code first", status=status.HTTP_400_BAD_REQUEST)
        all_policy.update(payment_policies=payment_policies)
        
        # Fetch return policies
        return_policies = eb.fetch_return_policies(access_token, marketplace_id)
        if type(return_policies) != dict:
           return Response(f"Failed to refresh access token. Get authorization code first", status=status.HTTP_400_BAD_REQUEST)
        all_policy.update(return_policies=return_policies)

        # Fetch Ebay store ID
        ebay_store_info = eb.get_ebay_user_id(access_token)
        if not ebay_store_info:
            return Response(f"Failed to fetch ebay store ID", status=status.HTTP_400_BAD_REQUEST)
        all_policy.update(ebay_store_id=ebay_store_info)
        
        return JsonResponse(all_policy, safe=False, status=status.HTTP_200_OK)

    
    # Enroll new marketplace 
    @api_view(['PUT'])
    # @permission_classes([IsAuthenticated])
    def complete_enrolment_or_update(request, userid, market_name):
        try:
            enrolment_list = get_object_or_404(MarketplaceEnronment, user_id=userid, marketplace_name=market_name)
            serializer = MarketplaceEnrolSerializer(instance=enrolment_list, data=request.data, partial=True)
            # serializer = MarketplaceEnrolSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
   
                return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Error: {e}", status=status.HTTP_400_BAD_REQUEST)
    
    # Get the enrolment detail from the enrolment table for editing
    @api_view(['GET'])
    def get_enrolment_detail(request, userid, market_name):
        try:
            ebay_info = list(MarketplaceEnronment.objects.all().filter(user_id=userid, marketplace_name=market_name).values())
        except Exception as e:
            return Response("User not register yet", status=status.HTTP_400_BAD_REQUEST)
        return JsonResponse({"marketplace_info":ebay_info}, safe=False, status=status.HTTP_200_OK)

    # Get all the required policies from Ebay for product listing.
    def get_all_policy_for_listing(self, userid, market_name, access_token):
        eb = Ebay()
        marketplace_id = "EBAY_US"
        all_policy = {}
        # Fetch fulfillment policies
        fulfillment_policies = eb.fetch_fulfillment_policies(access_token, marketplace_id)
        if type(fulfillment_policies) != dict:
            return Response(f"Failed to refresh access token. Get authorization code first", status=status.HTTP_400_BAD_REQUEST)
        all_policy.update(fulfillment_policies=fulfillment_policies)
        
        # Fetch payment policies
        payment_policies = eb.fetch_payment_policies(access_token, marketplace_id)
        if type(payment_policies) != dict:
            return Response(f"Failed to refresh access token. Get authorization code first", status=status.HTTP_400_BAD_REQUEST)
        all_policy.update(payment_policies=payment_policies)
        
        # Fetch return policies
        return_policies = eb.fetch_return_policies(access_token, marketplace_id)
        if type(return_policies) != dict:
           return Response(f"Failed to refresh access token. Get authorization code first", status=status.HTTP_400_BAD_REQUEST)
        all_policy.update(return_policies=return_policies)
        return all_policy
        

    # Create a connection to the eBay Trading API
    @api_view(['GET'])
    def get_product_to_list_detail(request, userid, market_name, prod_id):
        global product_id
        eb = Ebay()
        # refresh the refresh access_token
        access_token = eb.refresh_access_token(userid, market_name)
        try:
            # vendor_info = list(VendoEnronment.objects.all().filter(user_id=userid).values())
            product_details = list(Generalproducttable.objects.all().filter(id=prod_id, user_id=userid).values())
            enroll_id = product_details[0].get("enrollment_id")
            vendor_info = list(Enrollment.objects.all().filter(user_id=userid, id=enroll_id).values())
            ebay_info = list(MarketplaceEnronment.objects.all().filter(user_id=userid, marketplace_name=market_name).values())
            upc_code = product_details[0].get("upc")

            # Update the price of product with the calculated selling price
            try:
                start_price = eb.calculated_selling_price(enroll_id, product_details[0].get("total_product_cost"), product_details[0].get("id"), userid)
                if type(start_price) != float:
                    return Response(f"Failed to compute price, no valid data", status=status.HTTP_400_BAD_REQUEST)
                product_details[0]["selling_price"] = start_price
            except Exception as e:
                return Response(f"Failed to fetch data: {e}", status=status.HTTP_400_BAD_REQUEST)
            # Get the vendor's details of the product trying to list
            vendor_info[0]["vendor_location"] = list(Vendors.objects.all().filter(id=vendor_info[0].get("vendor_id")).values())
        except Exception as e:
            return JsonResponse({"Message":f"Failed to fetch product info: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        # Get the category id of the product
        category_info = eb.get_category_id_from_upc(upc_code, access_token)
        # Get all the policies for product listing
        all_policies = eb.get_all_policy_for_listing(userid, market_name, access_token)
        return JsonResponse({"product_info":product_details, "ebay_info":ebay_info, "vendor_details":vendor_info, "category_info":category_info, "policies_info":all_policies}, safe=False, status=status.HTTP_200_OK)

    # Get the category ID of a product using the UPC
    def get_category_id_from_upc(request, upc_code, access_token):
        url = 'https://api.ebay.com/buy/browse/v1/item_summary/search'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        params = {
            'q': upc_code,
            'limit': 1  # Limiting the results for simplicity
        }

        response = requests.get(url, headers=headers, params=params)
        response_data = response.json()

        try:
            item = response_data['itemSummaries'][0]
            category_id = item["categories"]
            return category_id
        except (KeyError, IndexError):
            return response_data

    # Function to retrieve leaf categories for a given category ID
    @api_view(['GET'])
    def get_leaf_category_id(request, userid, market_name, category_id):
        # Use '0' for the default US marketplace category tree
        eb = Ebay()
        category_tree_id = '0'
        leaf_category = []
        access_token = eb.refresh_access_token(userid, market_name)
        # eBay Taxonomy API endpoint to get subcategories
        url = f'https://api.ebay.com/commerce/taxonomy/v1/category_tree/{category_tree_id}/get_category_subtree?category_id={category_id}'

        # Set up headers with the OAuth token
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        # Make the GET request to fetch subcategories
        response = requests.get(url, headers=headers)

        # Check for any errors
        if response.status_code != 200:
            return JsonResponse({"Message":f"Failed to fetch leaf category: {response.content.decode()}"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            data = response.json()
            # Loop through and find leaf categories
            if "childCategoryTreeNodes" in data["categorySubtreeNode"]:
                for key in data["categorySubtreeNode"]["childCategoryTreeNodes"]: 
                    leaf_category.append(key['category'])
                return JsonResponse({"More_subcategory":leaf_category}, safe=False, status=status.HTTP_200_OK)
            else:
                # if no childCategoryTreeNodes, then that's the last leaf in the category.
                leaf_category.append(data["categorySubtreeNode"]['category'])
                return JsonResponse({"Last_subcategory":leaf_category}, safe=False, status=status.HTTP_200_OK)

    # Function to retrieve item specifics for a leaf category ID
    def get_item_specifics_from_ebay(request, access_token, leaf_category_id):
        # Use '0' for the default US marketplace category tree
        category_tree_id = '0'
        # eBay Taxonomy API endpoint
        url = f'https://api.ebay.com/commerce/taxonomy/v1/category_tree/{category_tree_id}/get_item_aspects_for_category?category_id={leaf_category_id}'

        # Set up headers with the OAuth token
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        # Make the GET request to fetch item specifics
        response = requests.get(url, headers=headers)

        # Check for any errors
        if response.status_code != 200:
            return JsonResponse({"Message":f"Failed to fetch item specific fields: {response.content.decode()}"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return response.json()
            
    @api_view(['GET'])
    def get_item_specifics_fields(request, userid, market_name, leaf_category_id):
        eb = Ebay()
        item_specifics_field = []
        choices_data = {}
        # refresh the refresh access_token
        access_token = eb.refresh_access_token(userid, market_name)
        if not access_token:
            return Response(f"Failed to refresh access token. Get authorization code first", status=status.HTTP_400_BAD_REQUEST)
        # Fetch item specifics from eBay and generate the serializer
        data = eb.get_item_specifics_from_ebay(access_token, leaf_category_id)
        # Pass the item specifics to the serializer generator function
        item_specifics = data.get('aspects', [])
        
        # Generate the dynamic serializer
        DynamicItemSpecificsSerializer, _fields, valid_choices_fields = ItemListingToEbaySerializer.generate_item_specifics_serializer(item_specifics)
        # Extract choices from the ChoiceField fields
        for field_name, field in DynamicItemSpecificsSerializer().fields.items():
            if isinstance(field, serializers.BooleanField) and field_name in _fields:
                item_specifics_field.append(field_name +" (Boolean field)")
            else:
                if field_name in _fields:
                    item_specifics_field.append(field_name)
        # item_specifics_field.append(choices_data)
        # For now, return the field names (you can replace this with form processing later)
        return Response({
            "item_specifics":item_specifics_field, "valid_choices":valid_choices_fields
        })
    
    # Calculate the selling price of product going to ebay
    def calculated_selling_price(self, enroll_id=0, start_price=0, prod_id='', userid=0):
        try:
            market_place = MarketplaceEnronment.objects.filter(user_id=userid)[0]
            enrollment = get_object_or_404(Enrollment, id=enroll_id, user_id=userid)
            if prod_id:
                product = Generalproducttable.objects.get(id=prod_id, user_id=userid)
            total_product_cost = float(start_price) + float(enrollment.fixed_markup) + ((int(enrollment.percentage_markup)/100) * float(start_price))
            selling_price = total_product_cost + float(market_place.fixed_markup) + ((float(market_place.fixed_percentage_markup)/100) * total_product_cost) + ((float(market_place.profit_margin)/100) * total_product_cost)
            if product.map:
                if selling_price < float(product.map):
                    selling_price = float(product.map)
        except Exception as e:
            return Response(f"Failed to fetch data: {e}", status=status.HTTP_400_BAD_REQUEST)
        return round(selling_price, 2)
        
    # Calculate the minimum offer price of product going to ebay
    def calculated_minimum_offer_price(self, enroll_id, prod_id, start_price, min_profit_mergin, profit_margin, userid):
        eb = Ebay()
        try:
            market_place = MarketplaceEnronment.objects.filter(user_id=userid)[0]
            selling_price = eb.calculated_selling_price(enroll_id, start_price, prod_id, userid)
            minimum_offer_price = selling_price + float(profit_margin) + ((int(min_profit_mergin)/100) * selling_price)
        except Exception as e:
            return Response(f"Failed to fetch data: {e}", status=status.HTTP_400_BAD_REQUEST)
        return round(minimum_offer_price, 2)
    
    # List product on Ebay
    def product_listing_to_ebay(self, userid, access_token, item_specifics_fields, validated_data, minimum_offer_price):
        eb = Ebay()
        # Root element for XML
        root = Element('ItemSpecifics')
        # Create a separate section for eBay item specifics
        for value in item_specifics_fields:
            inner_root_element = SubElement(root, 'NameValueList')
            name_element = SubElement(inner_root_element, 'Name')
            name_element.text = value
            value_element = SubElement(inner_root_element, 'Value')
            value_element.text = validated_data[value]
        # Convert the ElementTree to an XML string
        xml_item_specifice = tostring(root, encoding='unicode')
        
        # format the thumbnail images for listing
        picture_details = Element('PictureDetails')
        SubElement(picture_details, 'PictureURL').text = validated_data['picture_detail']
        if validated_data["thumbnailImage"] != "Null":
            thumbnail_images = validated_data["thumbnailImage"].strip('[]')  # Remove brackets
            thumbnail_images = [url.strip().strip('"') for url in thumbnail_images.split(',')]  # Split and clean URLs
            for img in thumbnail_images:
                SubElement(picture_details, 'PictureURL').text = img
        # Convert the ElementTree to an XML string
        item_image_url = tostring(picture_details, encoding='unicode')
        print(item_image_url)
        # Create a connection to the eBay Trading API
        api = Trading(
            appid = eb.app_id,
            certid = eb.cert_id,
            devid = eb.dev_id,
            token=access_token,
            config_file=None
        )

        # Define the item details
        item = f"""<Item>
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
                
                <!-- ... more PictureURL values allowed here ... -->
                {item_image_url}
                
                <!-- ... Item specifics are placed here ... -->
                {xml_item_specifice}
                
                <autoPay>false</autoPay>
                <PostalCode>{validated_data['postal_code']}</PostalCode>
                <Location>{validated_data['location']}</Location>
                <Country>US</Country>
                <Currency>USD</Currency>
                <ListingDuration>GTC</ListingDuration>
                {f'''<Charity>
                    <CharityID>{validated_data['charity_id']}</CharityID>
                    <DonationPercent>{validated_data['donation_percentage']}</DonationPercent>
                </Charity>''' if validated_data['enable_charity'] == True else ''}
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
                <bestOfferEnabled>{validated_data['bestOfferEnabled']}</bestOfferEnabled>
                <BestOfferDetails>
                  <BestOfferAutoAcceptPrice> {minimum_offer_price} </BestOfferAutoAcceptPrice>
                  <MinimumBestOfferPrice> {minimum_offer_price} </MinimumBestOfferPrice>
                </BestOfferDetails>
                <listingInfo>
                    <buyItNowAvailable>false</buyItNowAvailable>
                    <listingType>{validated_data['listingType']}</listingType>
                    <gift>{validated_data['gift']}</gift>
                    <watchCount>6</watchCount>
                </listingInfo>
                <CategoryMappingAllowed>{validated_data['categoryMappingAllowed']}</CategoryMappingAllowed>
                <IsMultiVariationListing>true</IsMultiVariationListing>
                <TopRatedListing>false</TopRatedListing>
            </Item>"""
        
        try:
            custom_fields = {}
            # Make the API call to add the item
            response = api.execute('AddFixedPriceItem', item)
            # Parse the XML
            namespace = {'ns': 'urn:ebay:apis:eBLBaseComponents'}
            root = ET.fromstring(response.text)
            
            # Extract Ack and ItemID
            ack = root.find('ns:Ack', namespace).text
            ebay_itemID = root.find('ns:ItemID', namespace).text
            # Put all the custom fields in the dictionary
            for value in item_specifics_fields:
                custom_fields[value] = validated_data[value]
            # save the listed product to inventory table
            item_listing, created = InventoryModel.objects.update_or_create(user_id=userid, sku=validated_data['sku'], defaults=dict(title=validated_data['title'], description=validated_data['description'], location=validated_data['location'], upc=validated_data['upc'], category_id=validated_data['category_id'], start_price=validated_data['start_price'], picture_detail=validated_data['picture_detail'], postal_code=validated_data['postal_code'], quantity=validated_data['quantity'], return_profileID=validated_data['return_profileID'], return_profileName=validated_data['return_profileName'], payment_profileID=validated_data['payment_profileID'], payment_profileName=validated_data['payment_profileName'], shipping_profileID=validated_data['shipping_profileID'], shipping_profileName=validated_data['shipping_profileName'], bestOfferEnabled=validated_data['bestOfferEnabled'], listingType=validated_data['listingType'], gift=validated_data['gift'], categoryMappingAllowed=validated_data['categoryMappingAllowed'], item_specific_fields=json.dumps(custom_fields), ebay_item_id=ebay_itemID, user_id=userid, product_id=validated_data['product'].id,  map_status=True, active=True, category=validated_data['category'], market_logos=validated_data['market_logos'], city=validated_data['city'], cost=validated_data['cost'], country=validated_data['country'], model=validated_data['model'], msrp=validated_data['msrp'], price=validated_data['price'], fixed_markup=validated_data['fixed_markup'], percentage_markup=validated_data['percentage_markup'], shipping_cost=validated_data['shipping_cost'], shipping_height=validated_data['shipping_height'], shipping_width=validated_data['shipping_width'], thumbnailImage=validated_data['thumbnailImage'], total_product_cost=validated_data['total_product_cost'], us_size=validated_data['us_size'], min_profit_mergin=validated_data['min_profit_mergin'], profit_margin=validated_data['profit_margin'], charity_id=validated_data['charity_id'], donation_percentage=validated_data['donation_percentage'], vendor_name=validated_data['vendor_name']))
           
            # Update the GeneralProduct table to set listed_market to true
            Generalproducttable.objects.filter(upc=validated_data['upc']).update(active=True)
            return Response(f"Product listing was successful {response.text}", status=status.HTTP_200_OK)
        except ConnectionError as e:       
            return Response(f"Failed to post connetion issue: {e}", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:       
            return Response(f"Failed to post: {e}", status=status.HTTP_400_BAD_REQUEST)
	
	
    # Function to save product for later listing
    @api_view(['POST'])
    def save_product_before_listing(self, userid, item_specifics_fields, validated_data):
        eb = Ebay()
        custom_fields = {}
       
        # Put all the custom fields in the dictionary
        for value in item_specifics_fields:
            custom_fields[value] = validated_data[value]
        
        # Get the calculated price of the product to list
        try:
            product_details = Generalproducttable.objects.all().filter(id=validated_data['product'].id, user_id=userid).values()
            enroll_id = product_details[0].get("enrollment_id")
            minimum_offer_price = eb.calculated_minimum_offer_price(enroll_id, validated_data['product'].id, validated_data['start_price'], validated_data['min_profit_mergin'], validated_data['profit_margin'], userid)
            if type(minimum_offer_price) != float:
                return Response(f"Failed to fetch data: minimum offer price error.", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(f"Failed to fetch data: {e}", status=status.HTTP_400_BAD_REQUEST)
        
        try:
            item_listing, created = InventoryModel.objects.update_or_create(user_id=userid, sku=validated_data['sku'], defaults=dict(title=validated_data['title'], description=validated_data['description'], location=validated_data['location'], upc=validated_data['upc'], category_id=validated_data['category_id'], start_price=validated_data['start_price'], picture_detail=validated_data['picture_detail'], postal_code=validated_data['postal_code'], quantity=validated_data['quantity'], return_profileID=validated_data['return_profileID'], return_profileName=validated_data['return_profileName'], payment_profileID=validated_data['payment_profileID'], payment_profileName=validated_data['payment_profileName'], shipping_profileID=validated_data['shipping_profileID'], shipping_profileName=validated_data['shipping_profileName'], bestOfferEnabled=validated_data['bestOfferEnabled'], listingType=validated_data['listingType'], gift=validated_data['gift'], categoryMappingAllowed=validated_data['categoryMappingAllowed'], item_specific_fields=json.dumps(custom_fields), user_id=userid, product_id=validated_data['product'].id,  map_status=True, active=False, category=validated_data['category'], market_logos=validated_data['market_logos'], city=validated_data['city'], cost=validated_data['cost'], country=validated_data['country'], model=validated_data['model'], msrp=validated_data['msrp'], price=validated_data['price'], fixed_markup=validated_data['fixed_markup'], percentage_markup=validated_data['percentage_markup'], shipping_cost=validated_data['shipping_cost'], shipping_height=validated_data['shipping_height'], shipping_width=validated_data['shipping_width'], thumbnailImage=validated_data['thumbnailImage'], total_product_cost=validated_data['total_product_cost'], us_size=validated_data['us_size'], min_profit_mergin=validated_data['min_profit_mergin'], profit_margin=validated_data['profit_margin'], charity_id=validated_data['charity_id'], donation_percentage=validated_data['donation_percentage'], vendor_name=validated_data['vendor_name']))
            # Update the GeneralProduct table to set listed_market to true
            Generalproducttable.objects.filter(upc=validated_data['upc']).update(active=True)
            return Response(f"Product saved was successful.", status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to post: {e}", status=status.HTTP_400_BAD_REQUEST)
 
        
        
    # Function to upload thumbnail image to cloudinary
    @api_view(['POST'])
    def upload_product_image(request, productid, product_name, userid):
        gen_val = random.randint(100, 100000)
        if request.method == 'POST':
            serializer = UploadedProductImageSerializer(data=request.data)
            if serializer.is_valid():
                # Upload an image
                image_file = request.FILES.get("image_url")
                upload_result = cloudinary.uploader.upload(image_file, public_id=f"{product_name}_{productid}_{gen_val}")
                # Optimize delivery by resizing and applying auto-format and auto-quality
                optimize_url, _ = cloudinary_url(f"{product_name}_{productid}_{gen_val}", fetch_format="auto", quality="auto")
                # Transform the image: auto-crop to square aspect_ratio
                auto_crop_url, _ = cloudinary_url(f"{product_name}_{productid}_{gen_val}", width=500, height=500, crop="auto", gravity="auto")
                save_image = UploadedProductImage(image_url=upload_result["secure_url"], image_name=upload_result["public_id"], product_id=productid, user_id=userid)
                save_image.save()
                return Response({"image_uploaded":upload_result}, status=201)
        return Response(serializer.errors, status=400)

    
    # Function to upload multiple images to cloudinary
    @api_view(['POST'])
    @parser_classes([MultiPartParser, FormParser])
    def upload_multiple_product_images(request, productid, product_name, userid):
        uploaded_urls = []
        if request.method == 'POST':
            serializer = UploadedProductImageSerializer(data=request.data)
            if serializer.is_valid():
                images = request.FILES.getlist("image_url")  # getlist() for multiple files
                if not images:
                    return Response({"error": "No images provided. Use key 'images' in form-data."}, status=400)

                for image_file in images:
                    # Generat a unique index for each image
                    gen_val = random.randint(100, 100000)
                    upload_result = cloudinary.uploader.upload(image_file, public_id=f"{product_name}_{productid}_{gen_val}")
                    # Optimize delivery by resizing and applying auto-format and auto-quality
                    optimize_url, _ = cloudinary_url(f"{product_name}_{productid}_{gen_val}", fetch_format="auto", quality="auto")
                    # Transform the image: auto-crop to square aspect_ratio
                    auto_crop_url, _ = cloudinary_url(f"{product_name}_{productid}_{gen_val}", width=500, height=500, crop="auto", gravity="auto")
                    # Append uploaded image details to list 
                    uploaded_urls.append({"image_url": upload_result["secure_url"]})
                
                # Save images to the database
                save_image = UploadedProductImage(image_url=json.dumps(uploaded_urls), image_name=product_name, product_id=productid, user_id=userid)
                save_image.save()

                return Response({
                    "message": "Images uploaded successfully",
                    "product": product_name,
                    "Total uploaded": len(uploaded_urls)
                    }, status=201)
            return Response(serializer.errors, status=400)


    # Get thumbnail image details
    @api_view(['GET'])
    def get_uploaded_image(request, productid, product_name, userid):
        save_image = UploadedProductImage.objects.filter(user_id=userid, product_id=productid).values()
        return JsonResponse({"image_data":list(save_image)}, safe=False, status=status.HTTP_200_OK)


    # Delete thumbnail image
    @api_view(['GET'])
    def delete_uploaded_image(request, image_name, image_id):
        # Delete the image from cloudinary first using the public ID of the image
        response = cloudinary.uploader.destroy(image_name)
        # Delete from the local table
        UploadedProductImage.objects.filter(id=image_id).delete()
        return Response(f"Image deleted successfully from thumbnail {response}", status=status.HTTP_200_OK)
      


class WooCommerce(APIView):
    # Enroll Woocommerce marketplace
    @api_view(['POST'])
    def woocommerce_enrollment(request, userid):
        # Check if the user is already enrolled in WooCommerce
        existing_enrollment = get_object_or_404(MarketplaceEnronment, user_id=userid, marketplace_name='WooCommerce')
        if existing_enrollment:
            return Response({"message": "User is already enrolled in WooCommerce"}, status=status.HTTP_400_BAD_REQUEST)

        # Pass request data to the dynamic serializer for validation
        serializer = WooComerceEnrolSerializer(data=request.data)      
        if serializer.is_valid():
            # Save the enrollment data to the database
            enrolment = serializer.save(user_id=userid)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  
        

    # Update Woocommerce marketplace 
    @api_view(['PUT'])
    # @permission_classes([IsAuthenticated])
    def update_woocommerce_enrolment(request, userid, market_name):
        try:
            enrolment_list = get_object_or_404(MarketplaceEnronment, user_id=userid, marketplace_name=market_name)
            serializer = WooComerceEnrolSerializer(instance=enrolment_list, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
   
                return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Error: {e}", status=status.HTTP_400_BAD_REQUEST)


    # Function to test your connection to Woocommerce
    @api_view(['GET'])
    def test_woocommerce_connection(request, userid, market_name):
        # enrolment_list = get_object_or_404(MarketplaceEnronment, user_id=userid, marketplace_name=market_name)
        # # Set up the WooCommerce API client
        # wcapi = API(
        #     url = enrolment_list.wc_consumer_url, 
        #     consumer_key = enrolment_list.wc_consumer_key,  
        #     consumer_secret = enrolment_list.wc_consumer_secret, 
        #     version = "wc/v3"
        # )
        r = requests.get("https://sozooutlet.com/",)
        return Response(f"Error: {r.text}", status=status.HTTP_400_BAD_REQUEST)


    # Get all product categories
    @api_view(['GET'])
    def get_product_category(request, userid, market_name):
        enrollment = MarketplaceEnronment.objects.get(user_id=userid, marketplace_name=market_name)
        # Set up the WooCommerce API client
        wcapi = API(
            url = enrollment.wc_consumer_url, 
            consumer_key = enrollment.wc_consumer_key,  
            consumer_secret = enrollment.wc_consumer_secret, 
            version = "wc/v3"
        )
        categories = wcapi.get("products/categories").json()
        return JsonResponse({"Product_categories":categories}, safe=False, status=status.HTTP_200_OK)
        # for cat in categories:
        #     print(f"ID: {cat['id']} | Name: {cat['name']} | Parent: {cat['parent']}")


    # Helper function to get category ID by name
    def get_category_id(self, category_name, url_, consumer_key_, consumer_secret_):
       # Set up the WooCommerce API client
        wcapi = API(
            url = url_, 
            consumer_key = consumer_key_,  
            consumer_secret = consumer_secret_, 
            version = "wc/v3"                # API version
        )
        """Return the category ID for a given category name."""
        categories = wcapi.get("products/categories").json()

        for cat in categories:
            if cat["name"].lower() == category_name.lower():
                return cat["id"]
        
        return None  # Not found


    # List product on Woocommerce
    @api_view(['POST'])
    def list_product_on_woocommerce(request, userid, market_name, category_name, validated_data):
        """Return the category ID for a given category name."""
        enrollment = MarketplaceEnronment.objects.get(user_id=userid, marketplace_name=market_name)
        # Set up the WooCommerce API client
        wcapi = API(
            url = enrollment.wc_consumer_url, 
            consumer_key = enrollment.wc_consumer_key,  
            consumer_secret = enrollment.wc_consumer_secret, 
            version = "wc/v3"
        )
       
        # Product payload mapped to WooCommerce
        product_data = {
            "name": validated_data['title'],
            "type": "simple",
            "regular_price": validated_data['start_price'],
            "description": validated_data['description'],
            "sku": validated_data['sku'],
            "stock_quantity": validated_data['quantity'],
            "manage_stock": True,
            "categories": [
                {"id": WooCommerce.get_category_id(category_name, enrollment.wc_consumer_url, enrollment.wc_consumer_key, enrollment.wc_consumer_secret)}   # Category ID must exist in WooCommerce
            ],
            "images": [
                {"src": validated_data['picture_detail']}
            ],
            "meta_data": [
                {"key": "UPC", "value": validated_data['upc']},
                {"key": "EAN", "value": validated_data['ean']},
                {"key": "ISBN", "value": validated_data['isbn']},
                {"key": "MPN", "value": validated_data['mpn']},

            ]
        }
        # Send POST request to WooCommerce to create the product
        response = wcapi.post("products", product_data).json()
        if response.status_code == 201:
            # Save the product to inventory table
            item_listing, created = InventoryModel.objects.update_or_create(user_id=userid, sku=validated_data['sku'], defaults=dict(title=validated_data['title'], description=validated_data['description'], location=validated_data['location'], upc=validated_data['upc'], category_id=validated_data['category_id'], start_price=validated_data['start_price'], picture_detail=validated_data['picture_detail'], postal_code=validated_data['postal_code'], quantity=validated_data['quantity'], return_profileID=validated_data['return_profileID'], return_profileName=validated_data['return_profileName'], payment_profileID=validated_data['payment_profileID'], payment_profileName=validated_data['payment_profileName'], shipping_profileID=validated_data['shipping_profileID'], shipping_profileName=validated_data['shipping_profileName'], bestOfferEnabled=validated_data['bestOfferEnabled'], listingType=validated_data['listingType'], gift=validated_data['gift'], categoryMappingAllowed=validated_data['categoryMappingAllowed'], item_specific_fields=json.dumps(product_data["meta_data"]), user_id=userid, product_id=validated_data['product'].id,  map_status=True, active=True, category=validated_data['category'], market_logos=validated_data['market_logos'], city=validated_data['city'], cost=validated_data['cost'], country=validated_data['country'], model=validated_data['model'], msrp=validated_data['msrp'], price=validated_data['price'], fixed_markup=validated_data['fixed_markup'], percentage_markup=validated_data['percentage_markup'], shipping_cost=validated_data['shipping_cost'], shipping_height=validated_data['shipping_height'], shipping_width=validated_data['shipping_width'], thumbnailImage=validated_data['thumbnailImage'], total_product_cost=validated_data['total_product_cost'], us_size=validated_data['us_size'], min_profit_mergin=validated_data['min_profit_mergin'], profit_margin=validated_data['profit_margin'], charity_id=validated_data['charity_id'], donation_percentage=validated_data['donation_percentage'], vendor_name=validated_data['vendor_name'], ))
            # Update the GeneralProduct table to set listed_market to true
            Generalproducttable.objects.filter(upc=validated_data['upc']).update(active=True)
            return Response(f"Product listing was successful {response.json()}", status=status.HTTP_200_OK)
        else:
            return Response(f"Failed to post: {response.json()}", status=status.HTTP_400_BAD_REQUEST)
        

    # Save product before listing on Woocommerce
    @api_view(['POST'])
    def save_product_before_listing(request, userid, category_name):
        eb = Ebay()
        # Generate the dynamic serializer by combining eBay fields and model fields (Product model)
        DynamicItemSpecificsSerializer = ItemListingToEbaySerializer.generate_woocommerce_listing_fields_serializer()
        # Pass request data to the dynamic serializer for validation
        serializer = DynamicItemSpecificsSerializer(data=request.data)          
        if serializer.is_valid():
            validated_data = serializer.validated_data
            # Get the calculated price of the product to list
            try:
                product_details = Generalproducttable.objects.all().filter(id=validated_data['product'].id, user_id=userid).values()
                enroll_id = product_details[0].get("enrollment_id")
                minimum_offer_price = eb.calculated_minimum_offer_price(enroll_id, validated_data['product'].id, validated_data['start_price'], validated_data['min_profit_mergin'], validated_data['profit_margin'], userid)
                if type(minimum_offer_price) != float:
                    return Response(f"Failed to fetch data: minimum offer price error.", status=status.HTTP_400_BAD_REQUEST)
                # Save the product to inventory table
                item_listing, created = InventoryModel.objects.update_or_create(user_id=userid, sku=validated_data['sku'], defaults=dict(title=validated_data['title'], description=validated_data['description'], location=validated_data['location'], upc=validated_data['upc'], category_id=validated_data['category_id'], start_price=validated_data['start_price'], picture_detail=validated_data['picture_detail'], postal_code=validated_data['postal_code'], quantity=validated_data['quantity'], bestOfferEnabled=validated_data['bestOfferEnabled'], listingType=validated_data['listingType'], gift=validated_data['gift'], categoryMappingAllowed=validated_data['categoryMappingAllowed'], user_id=userid, product_id=validated_data['product'].id,  map_status=True, active=False, category=validated_data['category'], market_logos=validated_data['market_logos'], city=validated_data['city'], cost=validated_data['cost'], country=validated_data['country'], model=validated_data['model'], msrp=validated_data['msrp'], price=validated_data['price'], fixed_markup=validated_data['fixed_markup'], percentage_markup=validated_data['percentage_markup'], shipping_cost=validated_data['shipping_cost'], shipping_height=validated_data['shipping_height'], shipping_width=validated_data['shipping_width'], thumbnailImage=validated_data['thumbnailImage'], total_product_cost=validated_data['total_product_cost'], us_size=validated_data['us_size'], min_profit_mergin=validated_data['min_profit_mergin'], profit_margin=validated_data['profit_margin'], charity_id=validated_data['charity_id'], donation_percentage=validated_data['donation_percentage'], vendor_name=validated_data['vendor_name']))
                # Update the GeneralProduct table to set listed_market to true
                Generalproducttable.objects.filter(upc=validated_data['upc']).update(active=True)
                return Response(f"Product saved was successful.", status=status.HTTP_200_OK)
            except Exception as e:
                return Response(f"Failed to fetch data: {e}", status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  
       


    @api_view(['GET'])
    def get_listed_products(request):
        wcm = WooCommerce()
        # Get all products
        products = wcm.wcapi.get("products").json()
        return JsonResponse({"Listed_products":products}, safe=False, status=status.HTTP_200_OK)