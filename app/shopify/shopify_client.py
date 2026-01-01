"""
Shopify API Client Module
Handles all interactions with the Shopify REST API
"""

import requests
from typing import Dict, List, Optional, Any, Tuple
from rich.console import Console
from rich.table import Table

console = Console()


class ShopifyClient:
    """Client for interacting with Shopify REST API"""
    
    def __init__(self, store_url: str, access_token: str):
        """
        Initialize Shopify client
        
        Args:
            store_url: Shopify store URL (e.g., 'yourstore.myshopify.com')
            access_token: Admin API access token
        """
        # Ensure store_url doesn't have protocol
        store_url = store_url.replace('https://', '').replace('http://', '').replace('/', '')
        if not store_url.endswith('.myshopify.com'):
            store_url = f"{store_url}.myshopify.com"
        
        # Use a stable API version - 2024-01 is valid, but let's ensure it's correct
        self.base_url = f"https://{store_url}/admin/api/2024-01"
        self.headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json"
        }
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make HTTP request to Shopify API"""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            # Store response for pagination info if needed
            self._last_response = response
            return response.json() if response.content else {}
        except requests.exceptions.HTTPError as e:
            if response.status_code == 400:
                # Bad Request - show detailed error
                console.print("[red]❌ Bad Request (400): Invalid request parameters.[/red]")
                try:
                    error_data = response.json()
                    error_msg = error_data.get("errors", error_data.get("error", error_data.get("message", "")))
                    if error_msg:
                        if isinstance(error_msg, dict):
                            console.print("\n[yellow]Error Details:[/yellow]")
                            for key, value in error_msg.items():
                                console.print(f"  • [red]{key}:[/red] {value}")
                        else:
                            console.print(f"[red]Error: {error_msg}[/red]")
                    # Show request details for debugging
                    console.print(f"\n[dim]Request URL: {url}[/dim]")
                    if params:
                        console.print(f"[dim]Parameters: {params}[/dim]")
                except:
                    console.print(f"[red]❌ Bad Request: {e}[/red]")
                    console.print(f"[dim]URL: {url}[/dim]")
            elif response.status_code == 401:
                console.print("[red]❌ Authentication failed. Please check your API token.[/red]")
            elif response.status_code == 404:
                console.print("[red]❌ Resource not found.[/red]")
            elif response.status_code == 422:
                # Validation error - show detailed error messages
                console.print("[red]❌ Validation Error: The request contains invalid data.[/red]")
                try:
                    error_data = response.json()
                    errors = error_data.get("errors", {})
                    if errors:
                        console.print("\n[yellow]Validation Errors:[/yellow]")
                        # Handle different error formats
                        if isinstance(errors, dict):
                            for field, messages in errors.items():
                                if isinstance(messages, list):
                                    for msg in messages:
                                        console.print(f"  • [red]{field}:[/red] {msg}")
                                else:
                                    console.print(f"  • [red]{field}:[/red] {messages}")
                        elif isinstance(errors, str):
                            console.print(f"  • {errors}")
                    else:
                        # Try to get error message from response
                        error_msg = error_data.get("error", str(e))
                        console.print(f"[red]Error: {error_msg}[/red]")
                except:
                    console.print(f"[red]❌ API Error: {e}[/red]")
            else:
                console.print(f"[red]❌ API Error: {e}[/red]")
                # Try to show error details if available
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", error_data.get("message", ""))
                    if error_msg:
                        console.print(f"[red]Details: {error_msg}[/red]")
                except:
                    pass
            return None
        except requests.exceptions.RequestException as e:
            console.print(f"[red]❌ Connection Error: {e}[/red]")
            return None
    
    def test_connection(self) -> bool:
        """Test if the API connection is working"""
        result = self._make_request("GET", "shop.json")
        return result is not None and "shop" in result
    
    def get_shop_info(self) -> Optional[Dict]:
        """Get shop information"""
        result = self._make_request("GET", "shop.json")
        return result.get("shop") if result else None
    
    # Product Methods
    def get_products(self, limit: int = 50, page_info: Optional[str] = None) -> Tuple[List[Dict], Optional[str]]:
        """
        Get list of products
        
        Returns:
            Tuple of (products list, next_page_info) or (empty list, None) on error
        """
        # Build params - only include valid parameters
        params = {}
        if limit and limit > 0:
            params["limit"] = min(int(limit), 250)  # Shopify max is 250
        
        # Only add page_info if it's provided and valid
        if page_info and page_info.strip():
            params["page_info"] = page_info.strip()
        
        # Only pass params if we have any, otherwise pass None to avoid empty dict issues
        if params:
            result = self._make_request("GET", "products.json", params=params)
        else:
            result = self._make_request("GET", "products.json")
        
        if result is None:
            return [], None
        
        products = result.get("products", [])
        # Get pagination info from response headers (Shopify uses Link header)
        next_page_info = None
        if hasattr(self, '_last_response'):
            link_header = self._last_response.headers.get('Link', '')
            # Parse Link header for next page info if present
            # Format: <url>; rel="next"
            if 'rel="next"' in link_header:
                # Extract page_info from URL if present
                pass  # Simplified for now
        return products, next_page_info
    
    def get_product(self, product_id: str) -> Optional[Dict]:
        """Get a single product by ID"""
        result = self._make_request("GET", f"products/{product_id}.json")
        return result.get("product") if result else None
    
    def create_product(self, product_data: Dict) -> Optional[Dict]:
        """Create a new product"""
        payload = {"product": product_data}
        result = self._make_request("POST", "products.json", data=payload)
        return result.get("product") if result else None
    
    def update_product(self, product_id: str, product_data: Dict) -> Optional[Dict]:
        """Update an existing product"""
        payload = {"product": product_data}
        result = self._make_request("PUT", f"products/{product_id}.json", data=payload)
        return result.get("product") if result else None
    
    def delete_product(self, product_id: str) -> bool:
        """Delete a product"""
        result = self._make_request("DELETE", f"products/{product_id}.json")
        return result is not None
    
    def add_product_to_collection(self, product_id: str, collection_id: str) -> bool:
        """Add a product to a collection"""
        collect_data = {
            "collect": {
                "product_id": int(product_id),
                "collection_id": int(collection_id)
            }
        }
        result = self._make_request("POST", "collects.json", data=collect_data)
        return result is not None and "collect" in result
    
    # Category/Collection Methods
    def get_collections(self, limit: int = 50) -> List[Dict]:
        """Get list of collections (categories)"""
        params = {"limit": limit}
        result = self._make_request("GET", "collections.json", params=params)
        return result.get("collections", []) if result else []
    
    def create_collection(self, collection_data: Dict) -> Optional[Dict]:
        """Create a new collection (category)"""
        payload = {"custom_collection": collection_data}
        result = self._make_request("POST", "custom_collections.json", data=payload)
        return result.get("custom_collection") if result else None
    
    def get_collection(self, collection_id: str) -> Optional[Dict]:
        """Get a single collection by ID"""
        result = self._make_request("GET", f"custom_collections/{collection_id}.json")
        return result.get("custom_collection") if result else None
    
    # Order Methods
    def get_orders(self, limit: int = 50, status: Optional[str] = None) -> List[Dict]:
        """Get list of orders"""
        params = {"limit": limit}
        if status:
            params["status"] = status
        result = self._make_request("GET", "orders.json", params=params)
        return result.get("orders", []) if result else []
    
    def get_order(self, order_id: str) -> Optional[Dict]:
        """Get a single order by ID"""
        result = self._make_request("GET", f"orders/{order_id}.json")
        return result.get("order") if result else None
    
    def update_order(self, order_id: str, order_data: Dict) -> Optional[Dict]:
        """Update an order"""
        payload = {"order": order_data}
        result = self._make_request("PUT", f"orders/{order_id}.json", data=payload)
        return result.get("order") if result else None
    
    # Inventory Methods
    def get_inventory_levels(self, location_ids: Optional[List[str]] = None) -> List[Dict]:
        """Get inventory levels"""
        params = {}
        if location_ids:
            params["location_ids"] = ",".join(location_ids)
        result = self._make_request("GET", "inventory_levels.json", params=params)
        return result.get("inventory_levels", []) if result else []
    
    def get_locations(self) -> List[Dict]:
        """Get store locations"""
        result = self._make_request("GET", "locations.json")
        return result.get("locations", []) if result else []

