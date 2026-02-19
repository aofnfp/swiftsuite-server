import requests
import json
import time
from django.core.cache import cache

def getFragranceXAuth(apiAccessId, apiAccessKey):
    cache_key = f"fx_token_{apiAccessId}"
    cached_token = cache.get(cache_key)
    if cached_token:
        return cached_token

    # API endpoint
    url = "https://apilisting.fragrancex.com/token"

    # Payload with the required parameters
    payload = {
        'grant_type': 'apiAccessKey',
        'apiAccessId': apiAccessId,  # Your API ID
        'apiAccessKey': apiAccessKey  # Your API Key
    }

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        response = requests.post(url, data=payload, headers=headers)
        # Raise an error if the request was unsuccessful
        response.raise_for_status()
        data = response.json()

        access_token = data.get("access_token")
        expires_in = data.get("expires_in", 3600) 
        cache.set(cache_key, access_token, timeout=expires_in - 60)  
        return access_token

    except requests.exceptions.RequestException as e:
        # Handle any errors that occur during the request
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
