
import requests
import base64
import os, json, random
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from rest_framework.decorators import api_view, parser_classes, permission_classes
from inventoryApp.models import InventoryModel
from rest_framework.permissions import IsAuthenticated, AllowAny
from ebaysdk.exception import ConnectionError
from vendorEnrollment.models import Generalproducttable, Enrollment
from xml.etree.ElementTree import Element, tostring, SubElement
from xml.etree import ElementTree as ET
from ebaysdk.trading import Connection as Trading
from datetime import datetime, timedelta
from marketplaceApp.views import Ebay



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
        response = requests.get(f"{url}?limit={limit}&offset={offset}", headers=HEADERS)
        data = response.json()
        if "inventoryItems" not in data:
            break
        items.extend(data["inventoryItems"])
        if len(data["inventoryItems"]) < limit:
            break
        offset += limit
    return items

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

    return all_orders


# ==== CALCULATE STATISTICS ====
@api_view(['GET'])
def generate_report(request, userId, date_range):
    eb = Ebay()
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
    return JsonResponse({"Active Listings": total_inventory, "Total Quantity in Inventory": total_quantity, f"Orders (Last {date_range} Days)": total_orders, "Total Items Sold": total_sold_items, "Total Sales": total_sales}, safe=False, status=status.HTTP_200_OK)

