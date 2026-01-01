"""
Shopify OAuth Module
Handles OAuth authentication flow for apps with client ID and client secret
"""

import requests
import urllib.parse
from typing import Optional, Dict
from rich.console import Console
from rich.panel import Panel

console = Console()


class ShopifyOAuth:
    """Handles Shopify OAuth authentication"""
    
    def __init__(self, store_url: str, client_id: str, client_secret: str, 
                 redirect_uri: Optional[str] = None,
                 scopes: str = "read_products,write_products,read_orders,write_orders,read_inventory,write_inventory"):
        """
        Initialize OAuth handler
        
        Args:
            store_url: Shopify store URL
            client_id: OAuth client ID
            client_secret: OAuth client secret
            redirect_uri: Redirect URI configured in your app (defaults to urn:ietf:wg:oauth:2.0:oob)
            scopes: Comma-separated list of scopes
        """
        # Clean store URL
        store_url = store_url.replace('https://', '').replace('http://', '').replace('/', '')
        if not store_url.endswith('.myshopify.com'):
            store_url = f"{store_url}.myshopify.com"
        
        self.store_url = store_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes
        # Use provided redirect_uri or default to out-of-band
        self.redirect_uri = redirect_uri or "urn:ietf:wg:oauth:2.0:oob"
    
    def get_authorization_url(self) -> str:
        """Generate authorization URL for user to visit"""
        params = {
            "client_id": self.client_id,
            "scope": self.scopes,
            "redirect_uri": self.redirect_uri
        }
        
        auth_url = f"https://{self.store_url}/admin/oauth/authorize?" + urllib.parse.urlencode(params)
        return auth_url
    
    def exchange_code_for_token(self, authorization_code: str) -> Optional[str]:
        """
        Exchange authorization code for access token
        
        Args:
            authorization_code: The authorization code from the OAuth callback
            
        Returns:
            Access token if successful, None otherwise
        """
        url = f"https://{self.store_url}/admin/oauth/access_token"
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": authorization_code
        }
        
        try:
            response = requests.post(url, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result.get("access_token")
        except requests.exceptions.HTTPError as e:
            console.print(f"[red]❌ Failed to exchange code: {e}[/red]")
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error_description", error_data.get("error", "Unknown error"))
                    console.print(f"[red]Error: {error_msg}[/red]")
                    if "redirect_uri" in error_msg.lower():
                        console.print("\n[yellow]⚠️  Redirect URI mismatch![/yellow]")
                        console.print("[yellow]Make sure the redirect URI matches what's configured in your Shopify app.[/yellow]")
                        console.print("[yellow]Location: Apps > Develop apps > Your App > App setup > Redirect URLs[/yellow]")
                except:
                    console.print("[red]Invalid authorization code or redirect URI mismatch.[/red]")
            return None
        except requests.exceptions.RequestException as e:
            console.print(f"[red]❌ Connection Error: {e}[/red]")
            return None



