from celery import shared_task
from .util import complete_enrolment_price_update



@shared_task(queue='default')
def complete_enrolment_price_update_task(userid, market_name):
    """Background task to check if eBay items have ended"""
    complete_enrolment_price_update(userid, market_name)
    return "Complete enrolment price update task finished successfully."


# # Function to refresh the access token using the refresh token
# def background_refresh_access_token(userid, market_name):
#     client_id = config("EB_CLIENT_ID")
#     client_secret = config("EB_CLIENT_SECRET")
#     token_url = "https://api.ebay.com/identity/v1/oauth2/token"
#     scopes = [
#             "https://api.ebay.com/oauth/api_scope",
#             "https://api.ebay.com/oauth/api_scope/sell.marketing.readonly",
#             "https://api.ebay.com/oauth/api_scope/sell.marketing",
#             "https://api.ebay.com/oauth/api_scope/sell.inventory.readonly",
#             "https://api.ebay.com/oauth/api_scope/sell.inventory",
#             "https://api.ebay.com/oauth/api_scope/sell.account.readonly",
#             "https://api.ebay.com/oauth/api_scope/sell.account",
#             "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly",
#             "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
#             "https://api.ebay.com/oauth/api_scope/sell.analytics.readonly",
#             "https://api.ebay.com/oauth/api_scope/sell.finances",
#             "https://api.ebay.com/oauth/api_scope/sell.payment.dispute",
#             "https://api.ebay.com/oauth/api_scope/commerce.identity.readonly",
#             "https://api.ebay.com/oauth/api_scope/sell.reputation",
#             "https://api.ebay.com/oauth/api_scope/sell.reputation.readonly",
#             "https://api.ebay.com/oauth/api_scope/commerce.notification.subscription",
#             "https://api.ebay.com/oauth/api_scope/commerce.notification.subscription.readonly",
#             "https://api.ebay.com/oauth/api_scope/sell.stores",
#             "https://api.ebay.com/oauth/api_scope/sell.stores.readonly"
#         ]


#     try:
#         connection = MarketplaceEnronment.objects.all().get(user_id=userid, marketplace_name=market_name)
#     except Exception as e:
#         return Response(f"Failed to fetch access token", status=status.HTTP_400_BAD_REQUEST)
    
#     access_token = connection.access_token
#     refresh_token = connection.refresh_token

#     credentials = f"{client_id}:{client_secret}"
#     credentials_base64 = base64.b64encode(credentials.encode()).decode()
    
#     headers = {
#         "Authorization": f"Basic {credentials_base64}",
#         "Content-Type": "application/x-www-form-urlencoded"
#     }
#     body = {
#         "grant_type": "refresh_token",
#         "refresh_token": refresh_token,
#         "scope": " ".join(scopes)  # Ensure scope is passed correctly
#     }

#     response = requests.post(token_url, headers=headers, data=body)
#     if response.status_code != 200:
#         return Response(f"Failed to refresh access token. Authorization code has expired", status=status.HTTP_400_BAD_REQUEST)

#     result = response.json()
#     access_token = result.get('access_token')
    
#     if not access_token:
#         return Response(f"Failed to get access token from response", status=status.HTTP_400_BAD_REQUEST)

#     MarketplaceEnronment.objects.filter(user_id=userid, marketplace_name=market_name).update(access_token=access_token, refresh_token=refresh_token)
#     return access_token
    


