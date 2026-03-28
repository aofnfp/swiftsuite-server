
import requests
import base64
import os, json, random
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from rest_framework.decorators import api_view, parser_classes, permission_classes
from inventoryApp.models import InventoryModel
from orderApp.models import OrdersOnEbayModel
from rest_framework.permissions import IsAuthenticated
from datetime import datetime, timedelta
from marketplaceApp.views import Ebay
from django.db.models import Sum
from accounts.permissions import IsOwnerOrHasPermission
from vendorEnrollment.utils import with_module



# ==== GET INVENTORY ITEMS (Active Listings) ====
def get_inventory_items(access_token):
    HEADERS = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
        }
    url = "https://api.ebay.com/sell/inventory/v1/inventory_item"
    items = []
    offset = 0
    limit = 50
    while True:
        try:
            response = requests.get(f"{url}?limit={limit}&offset={offset}", headers=HEADERS)
            data = response.json()
            if "inventoryItems" not in data:
                break
            items.extend(data["inventoryItems"])
            if len(data["inventoryItems"]) < limit:
                break
            offset += limit
            return items
        except Exception as e:
            return None

# ==== GET ORDERS ====
def get_orders(access_token, date_range='90'):
    
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
    start_time = (datetime.utcnow() - timedelta(days=int(date_range))).isoformat(timespec="seconds") + "Z"
    params = {
        "filter": f"creationdate:[{start_time}..]",
        "limit": limit
    }

    while True:
        try:
            params["offset"] = offset
            response = requests.get(base_url, headers=HEADERS, params=params)
            data = response.json()
            if "orders" not in data:
                break
            orders = data["orders"]
            all_orders.extend(orders)
            if len(orders) < limit:
                break
            offset += limit
        except Exception as e:
            return None

    return all_orders


# ==== CALCULATE STATISTICS ====
@with_module('reports')
@permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
@api_view(['GET'])
def generate_report(request, userId, date_range):
    # check if user is subaccount
    user = request.user
    if user:
        if user.parent_id:
            userId = user.parent_id

    eb = Ebay()
    try:
        access_token = eb.refresh_access_token(userId, "Ebay")

        inventory_items = get_inventory_items(access_token)
        orders = get_orders(access_token, date_range)
        # Inventory stats
        total_inventory = len(inventory_items)
        total_quantity = sum(
            item.get("availability", {}).get("shipToLocationAvailability", {}).get("quantity", 0)
            for item in inventory_items
        )

        # Order stats
        total_orders = len(orders)
        total_sold_items = sum(
            line["lineItems"][0].get("quantity", 0)
            for line in orders if "lineItems" in line and line["lineItems"]
        )
        total_sales = sum(
            float(line.get("pricingSummary", {}).get("total", {}).get("value", 0))
            for line in orders
        )
    except Exception as e:
        return Response(f"An error occurred, contact support team", status=status.HTTP_400_BAD_REQUEST)
    
    return JsonResponse({"Active Listings": total_inventory, "Total Quantity in Inventory": total_quantity, f"Orders (Last {date_range} Days)": total_orders, "Total Items Sold": total_sold_items, "Total Sales": round(total_sales, 4)}, safe=False, status=status.HTTP_200_OK)


@with_module('reports')
@permission_classes([IsAuthenticated, IsOwnerOrHasPermission])
@api_view(['GET'])
def sales_inventory_report(request, userId):
    # check if user is subaccount
    user = request.user
    if user:
        if user.parent_id:
            userId = user.parent_id

    inventory_report = InventoryModel.objects.filter(user_id=userId).values()
    inventory_report = (inventory_report.values('market_name').values('market_name').values('market_name').annotate(total_quantity=Sum('quantity')).values('market_name', 'quantity'))
    orders_report = OrdersOnEbayModel.objects.filter(user_id=userId).values()
    orders_report = (orders_report.values('vendor_name').values('vendor_name').values('vendor_name').annotate(total_quantity=Sum('quantity')).values('vendor_name', 'quantity'))
    return JsonResponse({"inventory_report": list(inventory_report), "orders_report": list(orders_report)}, safe=False, status=status.HTTP_200_OK)
