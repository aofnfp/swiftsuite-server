import requests
import json

def getFragranceXAuth(apiAccessId, apiAccessKey):
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
        # print("Access Token:", access_token)
        return access_token

    except requests.exceptions.RequestException as e:
        # Handle any errors that occur during the request
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

Username = None
Password = None
POS = 'I'

def getRSR(username, password, pos='I'):
    global Username, Password, POS  # Access the global variables

    # Set the global variables so they can be used in other functions
    Username = username
    Password = password
    POS = pos

    # API endpoint
    url = "https://www.rsrgroup.com/api/rsrbridge/1.0/pos/get-items"

    payload = {
        "Username":Username,
        "Password":Password,
        "POS":POS
    }
    

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        response = requests.post(url, data=payload, headers=headers)
        # Raise an error if the request was unsuccessful
        response.raise_for_status()
        data = response.json()
        Items = data.get("Items")
        return Items


    except requests.exceptions.RequestException as e:
        return None

def getRsrItemAttribute(upcCode):
    # API endpoint
    url = "https://www.rsrgroup.com/api/rsrbridge/1.0/pos/get-item-attributes"
    payload = {
        "Username":Username,
        "Password":Password,
        "POS":POS,
        "LookupBy": 'U',
        "UPCcode": upcCode
    }

    

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        response = requests.post(url, data=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        attribute = data.get("Attributes")
        data_string = json.dumps(attribute)
        return data_string
    except requests.exceptions.RequestException as e:
        return None
