# import requests
import json 

user_credentials = {
    'email': 'dami@gmail.com',
    'password': 'pass1234'
}

# # Make a request to obtain authentication token
# response = requests.post('http://127.0.0.1:8000/accounts/login/', data=user_credentials)
# token = response.json().get('access_token')  # Adjust to match the actual key returned by the token endpoint
# print(token)
# if token:
#     # Include the token in the request headers
#     headers = {'Authorization': f'Token {token}'}

#     # Make a request to the authenticated endpoint
#     response = requests.get('http://127.0.0.1:8000/vendor/vendor-enrolment/', headers=headers)
#     if response.status_code == 200:
#         try:
#             data = response.json()
#             print(data)
#         except requests.exceptions.JSONDecodeError:
#             print("Response is not valid JSON:", response.text)
#     else:
#         print("Request failed with status code:", response.status_code)


#     # Handle the response as needed
    
# else:
#     print("Failed to obtain authentication token")


[
    {"Name": "Caliber", "Value": "223 Remington"}, 
    {"Name": "Caliber", "Value": "556NATO"}, 
    {"Name": "Capacity", "Value": "30 Rounds"}, 
    {"Name": "Color", "Value": "Purple"}, 
    {"Name": "Fit", "Value": "AR Rifles"}, 
    {"Name": "Manufacturer Part #", "Value": "999-000-2320-54"}, 
    {"Name": "Model", "Value": "L5 Advanced Warfighter"}, 
    {"Name": "Subcategory", "Value": "Rifle Magazines"}, 
    {"Name": "Type", "Value": "Magazine"}
    
]

# Lipsey
# [
#     {'Name':'Action', 'Value':'Double Action Only'},
#     {'Name':'Barrellength' 'value':''}

# ]
[{"Name": "Model", "Value": "LCP"}, {"Name": "CaliberGauge", "Value": "380 ACP"}, {"Name": "Manufacturer", "Value": "Ruger"}, {"Name": "Type", "Value": "Semi-Auto Pistol"}, {"Name": "Action", "Value": "Double Action Only"}, {"Name": "BarrelLength", "Value": "2.75\""}, {"Name": "Capacity", "Value": "6+1"}, {"Name": "Finish", "Value": "Blue"}, {"Name": "OverallLength", "Value": "5.16\""}, {"Name": "Receiver", "Value": ""}, {"Name": "Safety", "Value": ""}, {"Name": "Sights", "Value": "Fixed Front & Rear"}, {"Name": "StockFrameGrips", "Value": "Polymer Frame Black Polymer Polymer Frame"}, {"Name": "Magazine", "Value": "1 6 rd."}, {"Name": "Weight", "Value": "9.4 oz."}, {"Name": "Chamber", "Value": ""}, {"Name": "DrilledAndTapped", "Value": "False"}, {"Name": "RateOfTwist", "Value": "1-in-16\" RH"}, {"Name": "ItemType", "Value": "Firearm"}, {"Name": "AdditionalFeature1", "Value": "Glass-Filled Nylon Frame"}, {"Name": "AdditionalFeature2", "Value": "3.6\" Overall Height"}, {"Name": "AdditionalFeature3", "Value": ".820\" Overall Width"}, {"Name": "ShippingWeight", "Value": "1.2"}, {"Name": "NfaThreadPattern", "Value": ""}, {"Name": "NfaAttachmentMethod", "Value": ""}, {"Name": "NfaBaffleType", "Value": ""}, {"Name": "SilencerCanBeDisassembled", "Value": "False"}, {"Name": "SilencerConstructionMaterial", "Value": ""}, {"Name": "NfaDbReduction", "Value": ""}, {"Name": "SilencerOutsideDiameter", "Value": ""}, {"Name": "NfaForm3Caliber", "Value": ""}, {"Name": "OpticMagnification", "Value": ""}, {"Name": "MaintubeSize", "Value": ""}, {"Name": "AdjustableObjective", "Value": "False"}, {"Name": "ObjectiveSize", "Value": ""}, {"Name": "OpticAdjustments", "Value": ""}, {"Name": "IlluminatedReticle", "Value": "False"}, {"Name": "Reticle", "Value": ""}, {"Name": "SightsType", "Value": ""}, {"Name": "Choke", "Value": ""}, {"Name": "DbReduction", "Value": ""}, {"Name": "FinishType", "Value": "Blued"}, {"Name": "Frame", "Value": "Polymer Frame"}, {"Name": "GripType", "Value": "Black Polymer"}, {"Name": "HandgunSlideMaterial", "Value": ""}, {"Name": "CountryOfOrigin", "Value": "US"}, {"Name": "ItemLength", "Value": "9.3"}, {"Name": "ItemWidth", "Value": "6"}, {"Name": "ItemHeight", "Value": "1.8"}]


[{"Name": "DimensionH", "Value": "0.5"}, {"Name": "DimensionL", "Value": "9"}, {"Name": "DimensionW", "Value": "5.5"}, {"Name": "Manufacturer", "Value": "ScientificAnglers"}, {"Name": "UPC Code", "Value": "840309102353"}, {"Name": "Weight", "Value": "0.17"}, {"Name": "Weight Units", "Value": "lb"}, {"Name": "Category", "Value": "Fishing"}, {"Name": "Subcategory", "Value": "FlyFishing"}, {"Name": "Shipping Weight", "Value": "0.18"}, {"Name": "Shipping Length", "Value": "7.9"}, {"Name": "Shipping Width", "Value": "3.85"}, {"Name": "Shipping Height", "Value": "0.85"}, {"Name": "Attribute 1", "Value": "Retractor:stretchesto15(38cm),pin-backattachment"}, {"Name": "Attribute 2", "Value": "Nipper,multi-purposetoolthathandlesmanytasks:hardenedsteelconstructionforlastingvalue,eyeopenerfeaturequicklyclearshookeyes,hardenededgestayssharperforreliablecutting"}, {"Name": "Attribute 3", "Value": "Forceps:locksecurelyinthreepositions,serratedjawsgraspsecurelyandholdon"}, {"Name": "Attribute 4", "Value": "Leaderstraightener:straightensleaderstoeliminatecoils,worksgreatonwetanddryleaders"}, {"Name": "Attribute 5", "Value": ""}, {"Name": "Attribute 6", "Value": ""}, {"Name": "Attribute 7", "Value": "123"}, {"Name": "Prop 65 Warning", "Value": "F"}, {"Name": "Prop 65 Reason", "Value": "N/A"}, {"Name": "Country of Origin", "Value": "US"}]