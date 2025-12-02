from warnings import filters
from django.shortcuts import render, redirect, get_object_or_404
import webbrowser
import requests
import base64
import os, json, random, re
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
import ast
from django.db.models import Q
from accounts.permissions import IsOwnerOrHasPermission
from vendorEnrollment.utils import with_module



# Function to list product on marketplace
@with_module('inventory')
@permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
@api_view(['POST'])
def listing_on_marketplace(request, userid, market_name, category_id_or_name):
    eb = Ebay()
    wooc = WooCommerce()
    item_specifics_fields = []
    try:
        access_token = eb.refresh_access_token(userid, market_name)
        if not access_token:
            return Response(f"Failed to refresh access token. Get authorization code first", status=status.HTTP_400_BAD_REQUEST)   
        # Fetch item specifics from eBay using the leaf category ID and generate the serializer
        if market_name == "Ebay":
            item_specifics_data = eb.get_item_specifics_from_ebay(access_token, int(category_id_or_name))
            if not item_specifics_data:
                return Response({"error": "Failed to fetch item specifics from eBay."}, status=status.HTTP_400_BAD_REQUEST)
        
            item_specifics = item_specifics_data.get('aspects', [])
            # Generate the dynamic serializer by combining eBay fields and model fields (Product model)
            DynamicItemSpecificsSerializer, item_specifics_fields, valid_choices_fields, required_fields = ItemListingToEbaySerializer.generate_item_specifics_serializer(item_specifics)
        else:
            DynamicItemSpecificsSerializer = ItemListingToEbaySerializer.generate_other_marketplace_listing_fields_serializer()
        
        # Pass request data to the dynamic serializer for validation
        serializer = DynamicItemSpecificsSerializer(data=request.data)      
        if serializer.is_valid():
            validated_data = serializer.validated_data
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  
    except Exception as e:
        return Response(f"Error error occurred in the form.", status=status.HTTP_400_BAD_REQUEST)     
    # Get the calculated price of the product to list
    try:
        product_details = Generalproducttable.objects.all().filter(id=validated_data['product'].id, user_id=userid).values()
        minimum_offer_price = eb.calculated_minimum_offer_price(validated_data['product'].id, validated_data['start_price'], validated_data['min_profit_mergin'], validated_data['profit_margin'], userid)
        if type(minimum_offer_price) != float:
            return Response(f"Failed to fetch data: minimum offer price error.", status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(f"Failed to fetch data check your enrollments:", status=status.HTTP_400_BAD_REQUEST)
    
    # Select the marketplace to list the product
    if market_name == "Ebay":
        return eb.product_listing_to_ebay(userid, access_token, item_specifics_fields, validated_data, minimum_offer_price)
    elif market_name == "Woocommerce":
        return wooc.list_product_on_woocommerce(userid, market_name, category_id_or_name, validated_data)
    elif market_name == "Shopify":
        pass
    elif market_name == "Amazon":
        pass
    elif market_name == "all":
        eb.product_listing_to_ebay(request, userid, market_name, int(category_id_or_name))
        wooc.list_product_on_woocommerce(request, userid, market_name, category_id_or_name)

# Function to save product before listing on marketplace
@with_module('inventory')
@permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
@api_view(['POST'])
def save_product_before_listing_on_marketplace(request, userid, market_name, category_id_or_name):
    eb = Ebay()
    wooc = WooCommerce()
    item_specifics_fields = []
    access_token = eb.refresh_access_token(userid, market_name)
    if not access_token:
        return Response(f"Failed to refresh access token. Get authorization code first", status=status.HTTP_400_BAD_REQUEST)   
    # Fetch item specifics from eBay using the leaf category ID and generate the serializer
    if market_name == "Ebay":
        item_specifics_data = eb.get_item_specifics_from_ebay(access_token, int(category_id_or_name))
        if not item_specifics_data:
            return Response({"error": "Failed to fetch item specifics from eBay."}, status=status.HTTP_400_BAD_REQUEST)
    
        item_specifics = item_specifics_data.get('aspects', [])
        # Generate the dynamic serializer by combining eBay fields and model fields (Product model)
        DynamicItemSpecificsSerializer, item_specifics_fields, valid_choices_fields, required_fields = ItemListingToEbaySerializer.generate_item_specifics_serializer(item_specifics)
    else:
        DynamicItemSpecificsSerializer = ItemListingToEbaySerializer.generate_other_marketplace_listing_fields_serializer()
    
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
        return Response(f"Failed to fetch data: Check your enrollments", status=status.HTTP_400_BAD_REQUEST)
    
    # Select the marketplace to list the product
    if market_name == "Ebay":
        return eb.save_product_before_listing(userid, item_specifics_fields, validated_data)
    elif market_name == "Woocommerce":
        return wooc.save_woocommerce_product_before_listing(userid, market_name, category_id_or_name, validated_data)
    elif market_name == "Shopify":
        pass
    elif market_name == "Amazon":
        pass
    elif market_name == "all":
        eb.product_listing_to_ebay(request, userid, market_name, int(category_id_or_name))
        wooc.list_product_on_woocommerce(request, userid, market_name, category_id_or_name)





class Ebay:
    
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

    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['POST'])
    def oauth_callback(request, userid, market_name):
        eb = Ebay()
        
        user = request.user
        if user:
            if user.is_subaccount:
                user = user.parent
            userid = user.id
        
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
        
        user = request.user
        if user:
            if user.is_subaccount:
                user = user.parent
            userid = user.id
        
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
                return Response(f"Failed to obtain access token:", status=status.HTTP_400_BAD_REQUEST)
            
            result = response.json()
            access_token = result.get('access_token')
            refresh_token = result.get('refresh_token')
            
            if not access_token:
                return Response(f"Failed to obtain access token from response", status=status.HTTP_400_BAD_REQUEST)
        except:
            return Response(f"Failed to obtain access token:", status=status.HTTP_400_BAD_REQUEST)

        obj, created = MarketplaceEnronment.objects.update_or_create(user_id=userid, marketplace_name=market_name, defaults={"access_token":access_token, "refresh_token":refresh_token})
        return access_token, refresh_token

    # Function to refresh the access token using the refresh token
    def refresh_access_token(self, userid, market_name):
        eb = Ebay()
        
        try:
            connection = MarketplaceEnronment.objects.all().get(user_id=userid, marketplace_name=market_name)
        except Exception as e:
            return Response(f"Failed to fetch access token", status=status.HTTP_400_BAD_REQUEST)
        
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
            return Response(f"Failed to refresh access token. Authorization code has expired", status=status.HTTP_400_BAD_REQUEST)

        result = response.json()
        access_token = result.get('access_token')
        
        if not access_token:
            return Response(f"Failed to get access token from response", status=status.HTTP_400_BAD_REQUEST)

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
            return JsonResponse({"Message":f"Failed to fetch fulfillment policies."}, status=status.HTTP_400_BAD_REQUEST)
        
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
            return JsonResponse({"Message":f"Failed to fetch payment policies."}, status=status.HTTP_400_BAD_REQUEST)

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
            return JsonResponse({"Message":f"Access token is invalid. Refreshing access token."}, status=status.HTTP_401_UNAUTHORIZED)
        elif response.status_code != 200:
            return JsonResponse({"Message":f"Failed to fetch shipping policies."}, status=status.HTTP_400_BAD_REQUEST)

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
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def refresh_connection_and_get_policy(request, userid, market_name):
        eb = Ebay()
        
        user = request.user
        if user:
            if user.is_subaccount:
                user = user.parent
            userid = user.id
        
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
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['PUT'])
    def complete_enrolment_or_update(request, userid, market_name):
        try:
            
            user = request.user
            if user:
                if user.is_subaccount:
                    user = user.parent
                userid = user.id
            
            enrolment_list = get_object_or_404(MarketplaceEnronment, user_id=userid, marketplace_name=market_name)
            serializer = MarketplaceEnrolSerializer(instance=enrolment_list, data=request.data, partial=True)
            # serializer = MarketplaceEnrolSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
   
                return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Error:", status=status.HTTP_400_BAD_REQUEST)
    
    # Get the enrolment detail from the enrolment table for editing
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_enrolment_detail(request, userid, market_name):
        try:
            
            user = request.user
            if user:
                if user.is_subaccount:
                    user = user.parent
                userid = user.id
                
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
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_product_to_list_detail(request, userid, market_name, prod_id):
        global product_id
        eb = Ebay()
        
        user = request.user
        if user:
            if user.is_subaccount:
                user = user.parent
            userid = user.id
        
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
                start_price = eb.calculated_selling_price(product_details[0].get("total_product_cost"), product_details[0].get("id"), userid)
                if type(start_price) != float:
                    return Response(f"Failed to compute price, no valid data", status=status.HTTP_400_BAD_REQUEST)
                product_details[0]["selling_price"] = start_price
            except Exception as e:
                return Response(f"Failed to fetch data: Check your enrollment details", status=status.HTTP_400_BAD_REQUEST)
            # Get the vendor's details of the product trying to list
            vendor_info[0]["vendor_location"] = list(Vendors.objects.all().filter(id=vendor_info[0].get("vendor_id")).values())
        except Exception as e:
            return JsonResponse({"Message":f"Failed to fetch product information."}, status=status.HTTP_400_BAD_REQUEST)
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
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_leaf_category_id(request, userid, market_name, category_id):
        # Use '0' for the default US marketplace category tree
        eb = Ebay()
        category_tree_id = '0'
        leaf_category = []
        
        user = request.user
        if user:
            if user.is_subaccount:
                user = user.parent
            userid = user.id
    
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
            return JsonResponse({"Message":f"Failed to fetch leaf category."}, status=status.HTTP_400_BAD_REQUEST)
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
            return JsonResponse({"Message":f"Failed to fetch item specific fields."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return response.json()

    
    # Function to get default category tree ID for a given marketplace
    def get_default_category_tree_id(self, oauth_token):
        url = "https://api.ebay.com/commerce/taxonomy/v1/get_default_category_tree_id"
        params = {"marketplace_id": "EBAY_US"}
        headers = {
            "Authorization": f"Bearer {oauth_token}",
            "Accept": "application/json",
        }

        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data["categoryTreeId"]


    # Function to get required item specifics for a given category
    def get_required_fields_item(self, category_id: str, access_token: str):
        eb = Ebay()
        category_tree_id = eb.get_default_category_tree_id(access_token)
        url = (
            f"https://api.ebay.com/commerce/taxonomy/v1_beta/"
            f"category_tree/{category_tree_id}/get_item_aspects_for_category"
        )
        params = {
            "category_id": category_id,
            "marketplace_id": "EBAY_US"
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        
        data = resp.json()
        required_aspects = []
        
        aspects = data.get("aspects", [])
        for aspect in aspects:
            constraint = aspect.get("aspectConstraint", {})
            if constraint.get("aspectRequired", False):
                required_aspects.append(aspect.get("localizedAspectName"))
        
        return required_aspects


    # Function to generate dynamic serializer for item specifics fields 
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])    
    @api_view(['GET'])
    def get_item_specifics_fields(request, userid, market_name, leaf_category_id):
        eb = Ebay()
        item_specifics_field = []
        choices_data = {}
        
        user = request.user
        if user:
            if user.is_subaccount:
                user = user.parent
            userid = user.id
            
        # refresh the refresh access_token
        access_token = eb.refresh_access_token(userid, market_name)
        if not access_token:
            return Response(f"Failed to refresh access token. Get authorization code first", status=status.HTTP_400_BAD_REQUEST)
        # Fetch item specifics from eBay and generate the serializer
        data = eb.get_item_specifics_from_ebay(access_token, leaf_category_id)
        
        # Pass the item specifics to the serializer generator function
        item_specifics = data.get('aspects', [])
        
        # Generate the dynamic serializer
        DynamicItemSpecificsSerializer, _fields, valid_choices_fields, required_fields = ItemListingToEbaySerializer.generate_item_specifics_serializer(item_specifics)
        # Extract choices from the ChoiceField fields
        for field_name, field in DynamicItemSpecificsSerializer().fields.items():
            if isinstance(field, serializers.BooleanField) and field_name in _fields:
                item_specifics_field.append(field_name +" (Boolean field)")
            else:
                if field_name in _fields:
                    item_specifics_field.append(field_name)
        
        # return the field names and their choices and required fields
        return Response({
            "item_specifics":item_specifics_field, "valid_choices":valid_choices_fields , "required_fields": required_fields
        })
    
    # Calculate the selling price of product going to marketplace
    def calculated_selling_price(self, start_price, prod_id, userid):
        try:
            market_place = MarketplaceEnronment.objects.filter(user_id=userid)[0]
            product = Generalproducttable.objects.get(id=prod_id, user_id=userid)
            selling_price = float(start_price) + float(market_place.fixed_markup) + ((float(market_place.fixed_percentage_markup)/100) *  float(start_price)) + ((float(market_place.profit_margin)/100) * float(start_price))
            if product.map:
                if selling_price < float(product.map):
                    selling_price = float(product.map)
        except Exception as e:
            return Response(f"Failed to fetch data: Check your enrollment details", status=status.HTTP_400_BAD_REQUEST)
        return round(selling_price, 2)
        
    # Calculate the minimum offer price of product going to ebay
    def calculated_minimum_offer_price(self, prod_id, start_price, min_profit_mergin, profit_margin, userid):
        eb = Ebay()
        try:
            selling_price = eb.calculated_selling_price(start_price, prod_id, userid)
            minimum_offer_price = selling_price + float(profit_margin) + ((int(min_profit_mergin)/100) * selling_price)
        except Exception as e:
            return Response(f"Failed to fetch data: Check your enrollment details", status=status.HTTP_400_BAD_REQUEST)
        return round(minimum_offer_price, 2)
    
    # List product on Ebay
    def product_listing_to_ebay(self, userid, access_token, item_specifics_fields, validated_data, minimum_offer_price):
        eb = Ebay()
        # Root element for XML
        try:
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
        except Exception as e:
            return Response(f"Failed to process item specifics: {e}", status=status.HTTP_400_BAD_REQUEST)
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
                {f'''<ProductListingDetails>
                  <UPC>{validated_data['upc']}</UPC>
                </ProductListingDetails>'''if validated_data['upc']!='Null' else ''}
                
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

            # if upc is null, set it to empty string
            if validated_data['upc'] == 'Null':
                validated_data['upc'] = ''
            # If the call was successful, save the item details to the inventory table
            item_listing, created = InventoryModel.objects.update_or_create(user_id=userid, sku=validated_data['sku'], defaults=dict(title=validated_data['title'], description=validated_data['description'], location=validated_data['location'], upc=validated_data['upc'], category_id=validated_data['category_id'], start_price=validated_data['start_price'], picture_detail=validated_data['picture_detail'], postal_code=validated_data['postal_code'], quantity=validated_data['quantity'], return_profileID=validated_data['return_profileID'], return_profileName=validated_data['return_profileName'], payment_profileID=validated_data['payment_profileID'], payment_profileName=validated_data['payment_profileName'], shipping_profileID=validated_data['shipping_profileID'], shipping_profileName=validated_data['shipping_profileName'], bestOfferEnabled=validated_data['bestOfferEnabled'], listingType=validated_data['listingType'], gift=validated_data['gift'], categoryMappingAllowed=validated_data['categoryMappingAllowed'], item_specific_fields=json.dumps(custom_fields), market_item_id=ebay_itemID, user_id=userid, product_id=validated_data['product'].id,  map_status=True, active=True, category=validated_data['category'], market_logos=validated_data['market_logos'], city=validated_data['city'], cost=validated_data['cost'], country=validated_data['country'], model=validated_data['model'], msrp=validated_data['msrp'], price=validated_data['price'], fixed_markup=validated_data['fixed_markup'], percentage_markup=validated_data['percentage_markup'], fixed_percentage_markup=validated_data['fixed_percentage_markup'], shipping_cost=validated_data['shipping_cost'], shipping_height=validated_data['shipping_height'], shipping_width=validated_data['shipping_width'], thumbnailImage=validated_data['thumbnailImage'], total_product_cost=validated_data['total_product_cost'], us_size=validated_data['us_size'], min_profit_mergin=validated_data['min_profit_mergin'], profit_margin=validated_data['profit_margin'], enable_charity=validated_data['enable_charity'], charity_id=validated_data['charity_id'], donation_percentage=validated_data['donation_percentage'], vendor_name=validated_data['vendor_name'], market_name="Ebay"))

            # Update the GeneralProduct table to set listed_market to true
            conditions = Q()
            if validated_data['upc']:
                conditions |= Q(upc=validated_data['upc'])
            if validated_data['sku']:
                conditions |= Q(sku=validated_data['sku'])

            Generalproducttable.objects.filter(conditions & Q(user_id=userid)).update(active=True)
            # Generalproducttable.objects.filter((Q(upc=validated_data['upc']) | Q(sku=validated_data['sku'])) & Q(user_id=userid)).update(active=True)
            return Response(f"Product listing was successful", status=status.HTTP_200_OK)
        except ConnectionError as e:
            clean_error = None
            match = re.search(r'Code:\s*\d+,\s*(.*)', str(e), re.DOTALL)
            if match:
                clean_error = match.group(1).strip()           
            return Response(f"Failed to post connection issue {clean_error}", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:  
            return Response(f"Failed to post: Check your input data", status=status.HTTP_400_BAD_REQUEST)
                
	
    # Function to save product for later listing
    def save_product_before_listing(self, userid, item_specifics_fields, validated_data):
        custom_fields = {}
       
        # Put all the custom fields in the dictionary
        for value in item_specifics_fields:
            custom_fields[value] = validated_data[value]
        
        # if upc is null, set it to empty string
        if validated_data['upc'] == 'Null':
            validated_data['upc'] = ''
        try:
            item_listing, created = InventoryModel.objects.update_or_create(user_id=userid, sku=validated_data['sku'], defaults=dict(title=validated_data['title'], description=validated_data['description'], location=validated_data['location'], upc=validated_data['upc'], category_id=validated_data['category_id'], start_price=validated_data['start_price'], picture_detail=validated_data['picture_detail'], postal_code=validated_data['postal_code'], quantity=validated_data['quantity'], return_profileID=validated_data['return_profileID'], return_profileName=validated_data['return_profileName'], payment_profileID=validated_data['payment_profileID'], payment_profileName=validated_data['payment_profileName'], shipping_profileID=validated_data['shipping_profileID'], shipping_profileName=validated_data['shipping_profileName'], bestOfferEnabled=validated_data['bestOfferEnabled'], listingType=validated_data['listingType'], gift=validated_data['gift'], categoryMappingAllowed=validated_data['categoryMappingAllowed'], item_specific_fields=json.dumps(custom_fields), user_id=userid, product_id=validated_data['product'].id,  map_status=True, active=False, category=validated_data['category'], market_logos=validated_data['market_logos'], city=validated_data['city'], cost=validated_data['cost'], country=validated_data['country'], model=validated_data['model'], msrp=validated_data['msrp'], price=validated_data['price'], fixed_markup=validated_data['fixed_markup'], percentage_markup=validated_data['percentage_markup'], fixed_percentage_markup=validated_data['fixed_percentage_markup'],  shipping_cost=validated_data['shipping_cost'], shipping_height=validated_data['shipping_height'], shipping_width=validated_data['shipping_width'], thumbnailImage=validated_data['thumbnailImage'], total_product_cost=validated_data['total_product_cost'], us_size=validated_data['us_size'], min_profit_mergin=validated_data['min_profit_mergin'], profit_margin=validated_data['profit_margin'], enable_charity=validated_data['enable_charity'], charity_id=validated_data['charity_id'], donation_percentage=validated_data['donation_percentage'], vendor_name=validated_data['vendor_name'], market_name="Ebay"))
            # Update the GeneralProduct table to set listed_market to true
            conditions = Q()
            if validated_data['upc']:
                conditions |= Q(upc=validated_data['upc'])
            if validated_data['sku']:
                conditions |= Q(sku=validated_data['sku'])

            Generalproducttable.objects.filter(conditions & Q(user_id=userid)).update(active=True)

            return Response(f"Product saved was successful.", status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Failed to post", status=status.HTTP_400_BAD_REQUEST)
 
        
        
    # Function to upload thumbnail image to cloudinary
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['POST'])
    def upload_product_image(request, productid, product_name, userid):
        gen_val = random.randint(100, 100000)
        
        user = request.user
        if user:
            if user.is_subaccount:
                user = user.parent
            userid = user.id
    
        if request.method == 'POST':
            serializer = UploadedProductImageSerializer(data=request.data)
            if serializer.is_valid():
                try:
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
                except:
                    return Response("Fail to upload image: Check your connection and try again.", status=400)
        return Response("Fail to upload image: Check your image file and try again.", status=400)

    
    # Function to upload multiple images to cloudinary
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['POST'])
    @parser_classes([MultiPartParser, FormParser])
    def upload_multiple_product_images(request, productid, product_name, userid):
        uploaded_urls = []
        
        user = request.user
        if user:
            if user.is_subaccount:
                user = user.parent
            userid = user.id
        
        if request.method == 'POST':
            serializer = UploadedProductImageSerializer(data=request.data)
            if serializer.is_valid():
                try:
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
                except:
                    return Response("Failed to upload image: Check your connection", status=400)
            return Response("Fail to upload image: Check your image file and try again.", status=400)


    # Get thumbnail image details
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_uploaded_image(request, productid, product_name, userid):
        try:
            
            user = request.user
            if user:
                if user.is_subaccount:
                    user = user.parent
                userid = user.id
            
            save_image = UploadedProductImage.objects.filter(user_id=userid, product_id=productid).values()
            return JsonResponse({"image_data":list(save_image)}, safe=False, status=status.HTTP_200_OK)
        except:
            return Response("Failed to retrieve image: Check your connection", status=400)

    # Delete thumbnail image
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def delete_uploaded_image(request, image_name, image_id):
        try:
            # Delete the image from cloudinary first using the public ID of the image
            response = cloudinary.uploader.destroy(image_name)
            # Delete from the local table
            UploadedProductImage.objects.filter(id=image_id).delete()
            return Response(f"Image deleted successfully from thumbnail", status=status.HTTP_200_OK)
        except:
            return Response("Failed to delete image: Check your connection", status=400)    
      


class WooCommerce:
    # Enroll Woocommerce marketplace
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['POST'])
    def woocommerce_enrollment(request, userid):
        # Check if the user is already enrolled in WooCommerce
        
        user = request.user
        if user:
            if user.is_subaccount:
                user = user.parent
            userid = user.id
        
        try:
            existing_enrollment = MarketplaceEnronment.objects.get(user_id=userid, marketplace_name='WooCommerce')
            return Response("User is already enrolled in WooCommerce marketplace.", status=status.HTTP_400_BAD_REQUEST)
        except MarketplaceEnronment.DoesNotExist:
            # Pass request data to the dynamic serializer for validation    
            serializer = WooComerceEnrolSerializer(data=request.data)      
            if serializer.is_valid():
                # Save the enrollment data to the database
                enrolment = serializer.save(user_id=userid)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response("Failed to enroll in WooCommerce marketplace: Check your input data", status=status.HTTP_400_BAD_REQUEST)
        

    # Update Woocommerce marketplace 
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['PUT'])
    # @permission_classes([IsAuthenticated])
    def update_woocommerce_enrolment(request, userid, market_name):
        try:
            
            user = request.user
            if user:
                if user.is_subaccount:
                    user = user.parent
                userid = user.id
            
            enrolment_list = get_object_or_404(MarketplaceEnronment, user_id=userid, marketplace_name=market_name)
            serializer = WooComerceEnrolSerializer(instance=enrolment_list, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
   
                return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Error: Update failed", status=status.HTTP_400_BAD_REQUEST)


    # Function to test your connection to Woocommerce
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def test_woocommerce_connection(request, userid, market_name):
        
        user = request.user
        if user:
            if user.is_subaccount:
                user = user.parent
            userid = user.id
        
        enrolment_list = get_object_or_404(MarketplaceEnronment, user_id=userid, marketplace_name=market_name)
        # Set up the WooCommerce API client
        wcapi = API(
            url = enrolment_list.wc_consumer_url, 
            consumer_key = enrolment_list.wc_consumer_key,  
            consumer_secret = enrolment_list.wc_consumer_secret, 
            version = "wc/v3"
        )
        # Step 3: Test WooCommerce REST endpoint
        try:
            response = wcapi.get("products").json()

            if isinstance(response, dict) and response.get("code") == "woocommerce_rest_cannot_view":
                return Response("Authentication failed: API key may not have permission.")
            elif isinstance(response, dict) and response.get("data", {}).get("status") == 401:
                return Response("Unauthorized: Check your Consumer Key/Secret.")
            elif isinstance(response, list):
                return Response(f"Credentials connected successfully!")
            else:
                return Response("Unexpected response:", response)
        except requests.exceptions.SSLError as e:
            return Response(f"SSL Error")
        except requests.exceptions.ConnectionError as e:
            return Response(f"Connection Error")
        except Exception as e:
            return Response(f"An error occurred")


    # Get all product categories
    @with_module('inventory')
    @permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
    @api_view(['GET'])
    def get_product_category(request, userid, market_name):
        try:
            user = request.user
            if user:
                if user.is_subaccount:
                    user = user.parent
                userid = user.id
                
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
        except Exception as e:
            return Response("Failed to fetch categories: Check your connection or credentials", status=status.HTTP_400_BAD_REQUEST)


    # Helper function to get category ID by name
    def get_category_id(self, category_name, url_, consumer_key_, consumer_secret_):
        try:
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
        except Exception as e:
            return Response("Failed to fetch categories: Check your connection or credentials", status=status.HTTP_400_BAD_REQUEST)


    # List product on Woocommerce
    def list_product_on_woocommerce(self, userid, market_name, category_name, validated_data):
        """Return the category ID for a given category name."""
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
            for key, value in ast.literal_eval(validated_data["item_specific_fields"]).items():
                meta_data.append({"key": key, "value": value})

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
                    {"id": wooc.get_category_id(category_name, enrollment.wc_consumer_url, enrollment.wc_consumer_key, enrollment.wc_consumer_secret)}   # Category ID must exist in WooCommerce
                ],
                "images": [
                    {"src": validated_data['picture_detail']}
                ],
                "meta_data": meta_data
            }
            # Send POST request to WooCommerce to create the product
            response = wcapi.post("products", product_data)
            if response.status_code == 201:
                # Save the product to inventory table
                item_listing, created = InventoryModel.objects.update_or_create(user_id=userid, sku=validated_data['sku'], defaults=dict(title=validated_data['title'], description=validated_data['description'], location=validated_data['location'], upc=validated_data['upc'], category_id=validated_data['category_id'], start_price=validated_data['start_price'], picture_detail=validated_data['picture_detail'], postal_code=validated_data['postal_code'], quantity=validated_data['quantity'], return_profileID=validated_data['return_profileID'], return_profileName=validated_data['return_profileName'], payment_profileID=validated_data['payment_profileID'], payment_profileName=validated_data['payment_profileName'], shipping_profileID=validated_data['shipping_profileID'], shipping_profileName=validated_data['shipping_profileName'], bestOfferEnabled=validated_data['bestOfferEnabled'], listingType=validated_data['listingType'], gift=validated_data['gift'], categoryMappingAllowed=validated_data['categoryMappingAllowed'], item_specific_fields=json.dumps(meta_data), user_id=userid, product_id=validated_data['product'].id,  map_status=True, active=True, category=validated_data['category'], market_logos=validated_data['market_logos'], city=validated_data['city'], cost=validated_data['cost'], country=validated_data['country'], model=validated_data['model'], msrp=validated_data['msrp'], price=validated_data['price'], fixed_markup=validated_data['fixed_markup'], percentage_markup=validated_data['percentage_markup'], shipping_cost=validated_data['shipping_cost'], shipping_height=validated_data['shipping_height'], shipping_width=validated_data['shipping_width'], thumbnailImage=validated_data['thumbnailImage'], total_product_cost=validated_data['total_product_cost'], us_size=validated_data['us_size'], min_profit_mergin=validated_data['min_profit_mergin'], profit_margin=validated_data['profit_margin'], charity_id=validated_data['charity_id'], donation_percentage=validated_data['donation_percentage'], vendor_name=validated_data['vendor_name'], market_name=market_name, woo_category_name=validated_data['woo_category_name'], market_item_id=response.json().get('id')))
                # Update the GeneralProduct table to set listed_market to true
                Generalproducttable.objects.filter((Q(upc=validated_data['upc']) | Q(sku=validated_data['sku'])) & Q(user_id=userid)).update(active=True)
                return Response(f"Product listing was successful.", status=status.HTTP_200_OK)
            else:
                return Response(f"Failed to post.", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(f"Failed to post: problem with your form fields", status=status.HTTP_400_BAD_REQUEST)
        

    # Save product before listing on Woocommerce
    def save_woocommerce_product_before_listing(self, userid, market_name, category_name, validated_data):
        try:
            # Generate the meta_data values from item specifics
            meta_data = []
            for key, value in ast.literal_eval(validated_data["item_specific_fields"]).items():
                meta_data.append({"key": key, "value": value})

            # Save the product to inventory table
            item_listing, created = InventoryModel.objects.update_or_create(user_id=userid, sku=validated_data['sku'], defaults=dict(title=validated_data['title'], description=validated_data['description'], location=validated_data['location'], upc=validated_data['upc'], category_id=validated_data['category_id'], start_price=validated_data['start_price'], picture_detail=validated_data['picture_detail'], postal_code=validated_data['postal_code'], quantity=validated_data['quantity'], return_profileID=validated_data['return_profileID'], return_profileName=validated_data['return_profileName'], payment_profileID=validated_data['payment_profileID'], payment_profileName=validated_data['payment_profileName'], shipping_profileID=validated_data['shipping_profileID'], shipping_profileName=validated_data['shipping_profileName'], bestOfferEnabled=validated_data['bestOfferEnabled'], listingType=validated_data['listingType'], gift=validated_data['gift'], categoryMappingAllowed=validated_data['categoryMappingAllowed'], item_specific_fields=json.dumps(meta_data), user_id=userid, product_id=validated_data['product'].id,  map_status=True, active=False, category=validated_data['category'], market_logos=validated_data['market_logos'], city=validated_data['city'], cost=validated_data['cost'], country=validated_data['country'], model=validated_data['model'], msrp=validated_data['msrp'], price=validated_data['price'], fixed_markup=validated_data['fixed_markup'], percentage_markup=validated_data['percentage_markup'], shipping_cost=validated_data['shipping_cost'], shipping_height=validated_data['shipping_height'], shipping_width=validated_data['shipping_width'], thumbnailImage=validated_data['thumbnailImage'], total_product_cost=validated_data['total_product_cost'], us_size=validated_data['us_size'], min_profit_mergin=validated_data['min_profit_mergin'], profit_margin=validated_data['profit_margin'], charity_id=validated_data['charity_id'], donation_percentage=validated_data['donation_percentage'], vendor_name=validated_data['vendor_name'], market_name=market_name, woo_category_name=validated_data['woo_category_name']))
            # Update the GeneralProduct table to set listed_market to true
            Generalproducttable.objects.filter((Q(upc=validated_data['upc']) | Q(sku=validated_data['sku'])) & Q(user_id=userid)).update(active=True)
            return Response(f"Product saved was successful.", status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Fail to save product.", status=status.HTTP_400_BAD_REQUEST)
        

    