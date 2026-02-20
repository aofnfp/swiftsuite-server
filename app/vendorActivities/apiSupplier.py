import requests
import json
import time
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


# Official FragranceX rate limits:
#   3 req/second  — enforced by time.sleep(0.4) in the Celery task loop
#   300 req/hour  — enforced by the cache counter below
#   500 req/endpoint/day — enforced by the daily counter below
FX_TRACKING_HOURLY_LIMIT = 285
FX_TRACKING_DAILY_LIMIT = 490


def frxLimitCounter(api_id):
    hourly_key = f"fx_hourly_{api_id}"
    daily_key  = f"fx_daily_{api_id}"

    # Initialize safely
    if cache.get(hourly_key) is None:
        cache.set(hourly_key, 0, timeout=3600)

    if cache.get(daily_key) is None:
        cache.set(daily_key, 0, timeout=86400)

    try:
        hourly_count = cache.incr(hourly_key)
        daily_count  = cache.incr(daily_key)
    except ValueError:
        # Key expired between get and incr
        cache.set(hourly_key, 1, timeout=3600)
        cache.set(daily_key, 1, timeout=86400)
        hourly_count = 1
        daily_count = 1

    # Check limits
    if hourly_count > FX_TRACKING_HOURLY_LIMIT:
        cache.decr(hourly_key)
        logger.warning(
            f"FX hourly quota reached ({hourly_count - 1}/{FX_TRACKING_HOURLY_LIMIT}) "
            f"for api_id={api_id}"
        )
        return False

    if daily_count > FX_TRACKING_DAILY_LIMIT:
        cache.decr(daily_key)
        logger.warning(
            f"FX daily quota reached ({daily_count - 1}/{FX_TRACKING_DAILY_LIMIT}) "
            f"for api_id={api_id}"
        )
        return False

    return True



def getFragranceXAuth(apiAccessId, apiAccessKey):
    cache_key = f"fx_token_{apiAccessId}"
    cached_token = cache.get(cache_key)
    if cached_token:
        return cached_token

    # API endpoint
    url = "https://apilisting.fragrancex.com/token"

    payload = {
        'grant_type': 'apiAccessKey',
        'apiAccessId': apiAccessId,  
        'apiAccessKey': apiAccessKey  
    }

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        response = requests.post(url, data=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        access_token = data.get("access_token")
        expires_in = data.get("expires_in", 3600) 
        cache.set(cache_key, access_token, timeout=expires_in - 60)  
        return access_token

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

def getFragranceXData(apiAccessId, apiAccessKey):
    # Get the access token
    access_token = getFragranceXAuth(apiAccessId, apiAccessKey)

    url = "https://apilisting.fragrancex.com/product/list"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data
    except:
        return None




URL = "https://www.rsrgroup.com/api/rsrbridge/1.0/pos/get-items"

def fetch_rsr_chunk(username, password, pos, offset, limit=25):
    
    payload = {
        "Username": username,
        "Password": password,
        "POS": pos,
        "WithAttributes": True,
        "Limit": limit,
        "Offset": offset
    }

    headers = {"Content-Type": "application/json"}

    response = requests.post(URL, json=payload, timeout=30)
    if response.status_code == 500:
        raise Exception("RSR internal server error")
    
    response.raise_for_status()
    data = response.json()
    return data.get("Items", [])


def getRSRWithAttr(username, password, pos="I"):
    offset = 0
    limit = 500
    all_items = []
    MAX_RETRIES = 5

    while True:
        retries = 0
        
        while retries < MAX_RETRIES:
            try:
                items = fetch_rsr_chunk(username, password, pos, offset, limit)
                break
            except Exception as e:
                retries += 1
                print(f"Retry {retries} for offset {offset}: {e}")
                time.sleep(2 ** retries)

        if retries == MAX_RETRIES:
            raise RuntimeError(f"Failed permanently at offset {offset}")

        if not items:
            break

        all_items.extend(items)
        offset += limit

        
        time.sleep(0.2)
        print(len(all_items), "- total item")
    return all_items



def getRSR(username, password, pos='I'):
    
    payload = {
        "Username":username,
        "Password":password,
        "POS":pos,
    }
    
    try:
        response = requests.post(URL, data=payload)
        # Raise an error if the request was unsuccessful
        response.raise_for_status()
        data = response.json()
        Items = data.get("Items")
        return Items


    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None



# def getRsrItemAttribute(upcCode):
#     # API endpoint
#     url = "https://www.rsrgroup.com/api/rsrbridge/1.0/pos/get-item-attributes"
#     payload = {
#         "Username":Username,
#         "Password":Password,
#         "POS":POS,
#         "LookupBy": 'U',
#         "UPCcode": upcCode
#     }

    

#     headers = {
#         'Content-Type': 'application/x-www-form-urlencoded'
#     }

#     try:
#         response = requests.post(url, data=payload, headers=headers)
#         response.raise_for_status()
#         data = response.json()
#         attribute = data.get("Attributes")
#         data_string = json.dumps(attribute)
#         print(upcCode)
#         return data_string
#     except requests.exceptions.RequestException as e:
#         print(f"An error occurred: {e}")
#         return None
