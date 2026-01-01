"""
Order Management Module
Handles order operations (fetch, update, track)
"""

from typing import Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from datetime import datetime
from shopify_client import ShopifyClient

console = Console()


class OrderManager:
    """Manages order operations"""
    
    def __init__(self, client: ShopifyClient):
        """Initialize order manager with Shopify client"""
        self.client = client
    
    def list_orders(self, limit: int = 50, status: Optional[str] = None):
        """List all orders"""
        status_text = f" ({status})" if status else ""
        console.print(f"[cyan]📋 Fetching orders{status_text}...[/cyan]")
        orders = self.client.get_orders(limit=limit, status=status)
        
        if not orders:
            console.print("[yellow]No orders found.[/yellow]")
            return []
        
        table = Table(title=f"Orders{status_text}", show_header=True, header_style="bold magenta")
        table.add_column("Order #", style="cyan", width=10)
        table.add_column("Name", style="green", width=15)
        table.add_column("Email", style="blue", width=25)
        table.add_column("Total", style="magenta", width=12)
        table.add_column("Status", style="yellow", width=15)
        table.add_column("Date", style="white", width=20)
        
        for order in orders:
            created_date = order.get("created_at", "")
            if created_date:
                try:
                    dt = datetime.fromisoformat(created_date.replace("Z", "+00:00"))
                    created_date = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
            
            table.add_row(
                f"#{order.get('order_number', 'N/A')}",
                order.get("name", "N/A"),
                order.get("email", "N/A")[:25],
                f"${order.get('total_price', '0')}",
                order.get("financial_status", "N/A"),
                created_date
            )
        
        console.print(table)
        return orders
    
    def show_order_details(self, order_id: str):
        """Show detailed information about an order"""
        console.print(f"[cyan]📋 Fetching order {order_id}...[/cyan]")
        order = self.client.get_order(order_id)
        
        if not order:
            console.print("[red]❌ Order not found.[/red]")
            return
        
        # Format dates
        created_date = order.get("created_at", "N/A")
        updated_date = order.get("updated_at", "N/A")
        
        try:
            if created_date != "N/A":
                dt = datetime.fromisoformat(created_date.replace("Z", "+00:00"))
                created_date = dt.strftime("%Y-%m-%d %H:%M:%S")
            if updated_date != "N/A":
                dt = datetime.fromisoformat(updated_date.replace("Z", "+00:00"))
                updated_date = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
        
        # Order details
        details = f"""
[bold]Order Number:[/bold] #{order.get('order_number', 'N/A')}
[bold]Name:[/bold] {order.get('name', 'N/A')}
[bold]Email:[/bold] {order.get('email', 'N/A')}
[bold]Total:[/bold] ${order.get('total_price', '0')}
[bold]Subtotal:[/bold] ${order.get('subtotal_price', '0')}
[bold]Tax:[/bold] ${order.get('total_tax', '0')}
[bold]Shipping:[/bold] ${order.get('total_shipping_price_set', {}).get('shop_money', {}).get('amount', '0')}
[bold]Financial Status:[/bold] {order.get('financial_status', 'N/A')}
[bold]Fulfillment Status:[/bold] {order.get('fulfillment_status', 'N/A')}
[bold]Created:[/bold] {created_date}
[bold]Updated:[/bold] {updated_date}
"""
        
        # Shipping address
        shipping_address = order.get("shipping_address", {})
        if shipping_address:
            details += f"""
[bold]Shipping Address:[/bold]
  {shipping_address.get('name', '')}
  {shipping_address.get('address1', '')}
  {shipping_address.get('city', '')}, {shipping_address.get('province', '')} {shipping_address.get('zip', '')}
  {shipping_address.get('country', '')}
"""
        
        console.print(Panel(details, title="Order Details", border_style="green"))
        
        # Show line items
        line_items = order.get("line_items", [])
        if line_items:
            items_table = Table(title="Order Items", show_header=True, header_style="bold cyan")
            items_table.add_column("Product", style="green", width=30)
            items_table.add_column("Variant", style="blue", width=20)
            items_table.add_column("Quantity", style="yellow", width=10)
            items_table.add_column("Price", style="magenta", width=12)
            items_table.add_column("Total", style="red", width=12)
            
            for item in line_items:
                items_table.add_row(
                    item.get("title", "N/A")[:30],
                    item.get("variant_title", "N/A")[:20] or "Default",
                    str(item.get("quantity", 0)),
                    f"${item.get('price', '0')}",
                    f"${float(item.get('price', 0)) * item.get('quantity', 0):.2f}"
                )
            
            console.print(items_table)
    
    def update_order(self, order_id: str, **kwargs):
        """Update an order"""
        order_data = {}
        
        if "note" in kwargs:
            order_data["note"] = kwargs["note"]
        if "tags" in kwargs:
            order_data["tags"] = kwargs["tags"]
        if "financial_status" in kwargs:
            order_data["financial_status"] = kwargs["financial_status"]
        
        if not order_data:
            console.print("[yellow]⚠️  No fields to update.[/yellow]")
            return None
        
        console.print(f"[cyan]📋 Updating order {order_id}...[/cyan]")
        order = self.client.update_order(order_id, order_data)
        
        if order:
            console.print(f"[green]✅ Order updated successfully![/green]")
            return order
        else:
            console.print("[red]❌ Failed to update order.[/red]")
            return None
    
    def track_order(self, order_id: str):
        """Track order status and fulfillment"""
        console.print(f"[cyan]📦 Tracking order {order_id}...[/cyan]")
        order = self.client.get_order(order_id)
        
        if not order:
            console.print("[red]❌ Order not found.[/red]")
            return
        
        # Order tracking info
        tracking_info = f"""
[bold]Order Status:[/bold] {order.get('financial_status', 'N/A')}
[bold]Fulfillment Status:[/bold] {order.get('fulfillment_status', 'N/A') or 'Unfulfilled'}
[bold]Order Number:[/bold] #{order.get('order_number', 'N/A')}
"""
        
        # Fulfillment tracking
        fulfillments = order.get("fulfillments", [])
        if fulfillments:
            tracking_info += "\n[bold]Fulfillment Tracking:[/bold]\n"
            for fulfillment in fulfillments:
                tracking_info += f"""
  [bold]Status:[/bold] {fulfillment.get('status', 'N/A')}
  [bold]Tracking Company:[/bold] {fulfillment.get('tracking_company', 'N/A')}
  [bold]Tracking Number:[/bold] {fulfillment.get('tracking_number', 'N/A')}
  [bold]Tracking URL:[/bold] {fulfillment.get('tracking_url', 'N/A')}
"""
        else:
            tracking_info += "\n[yellow]No fulfillment information available.[/yellow]"
        
        console.print(Panel(tracking_info, title="Order Tracking", border_style="cyan"))

