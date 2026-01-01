"""
Inventory Management Module
Handles inventory level tracking and management
"""

from typing import Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from shopify_client import ShopifyClient

console = Console()


class InventoryManager:
    """Manages inventory operations"""
    
    def __init__(self, client: ShopifyClient):
        """Initialize inventory manager with Shopify client"""
        self.client = client
    
    def list_inventory_levels(self, location_ids: Optional[List[str]] = None):
        """List inventory levels for all locations"""
        console.print("[cyan]📊 Fetching inventory levels...[/cyan]")
        
        # Get locations if not provided
        if not location_ids:
            locations = self.client.get_locations()
            if locations:
                location_ids = [str(loc.get("id")) for loc in locations]
        
        inventory_levels = self.client.get_inventory_levels(location_ids)
        
        if not inventory_levels:
            console.print("[yellow]No inventory levels found.[/yellow]")
            return []
        
        table = Table(title="Inventory Levels", show_header=True, header_style="bold magenta")
        table.add_column("Location ID", style="cyan", width=12)
        table.add_column("Inventory Item ID", style="blue", width=15)
        table.add_column("Available", style="green", width=12)
        table.add_column("Updated", style="yellow", width=20)
        
        for level in inventory_levels:
            table.add_row(
                str(level.get("location_id", "N/A")),
                str(level.get("inventory_item_id", "N/A")),
                str(level.get("available", 0)),
                level.get("updated_at", "N/A")[:19] if level.get("updated_at") else "N/A"
            )
        
        console.print(table)
        return inventory_levels
    
    def list_locations(self):
        """List all store locations"""
        console.print("[cyan]📍 Fetching store locations...[/cyan]")
        locations = self.client.get_locations()
        
        if not locations:
            console.print("[yellow]No locations found.[/yellow]")
            return []
        
        table = Table(title="Store Locations", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=10)
        table.add_column("Name", style="green", width=30)
        table.add_column("Address", style="blue", width=40)
        table.add_column("Active", style="yellow", width=10)
        
        for location in locations:
            address = location.get("address1", "")
            if location.get("city"):
                address += f", {location.get('city')}"
            
            table.add_row(
                str(location.get("id", "")),
                location.get("name", "N/A"),
                address[:40] if address else "N/A",
                "Yes" if location.get("active", False) else "No"
            )
        
        console.print(table)
        return locations
    
    def show_location_details(self, location_id: str):
        """Show detailed information about a location"""
        console.print(f"[cyan]📍 Fetching location {location_id}...[/cyan]")
        locations = self.client.get_locations()
        
        location = None
        for loc in locations:
            if str(loc.get("id")) == str(location_id):
                location = loc
                break
        
        if not location:
            console.print("[red]❌ Location not found.[/red]")
            return
        
        address = location.get("address1", "")
        if location.get("address2"):
            address += f"\n{location.get('address2')}"
        if location.get("city"):
            address += f"\n{location.get('city')}, {location.get('province')} {location.get('zip')}"
        if location.get("country"):
            address += f"\n{location.get('country')}"
        
        details = f"""
[bold]Name:[/bold] {location.get('name', 'N/A')}
[bold]Active:[/bold] {'Yes' if location.get('active', False) else 'No'}
[bold]Address:[/bold]
{address}
[bold]Phone:[/bold] {location.get('phone', 'N/A')}
[bold]Created:[/bold] {location.get('created_at', 'N/A')[:19] if location.get('created_at') else 'N/A'}
"""
        
        console.print(Panel(details, title="Location Details", border_style="green"))

