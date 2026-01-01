"""
Category Management Module
Handles collection/category operations
"""

from typing import Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from shopify_client import ShopifyClient

console = Console()


class CategoryManager:
    """Manages category/collection operations"""
    
    def __init__(self, client: ShopifyClient):
        """Initialize category manager with Shopify client"""
        self.client = client
        self._cached_collections = None
    
    def list_categories(self, refresh: bool = False):
        """List all categories (collections)"""
        if refresh or self._cached_collections is None:
            console.print("[cyan]🏷️  Fetching categories...[/cyan]")
            self._cached_collections = self.client.get_collections()
        
        if not self._cached_collections:
            console.print("[yellow]No categories found.[/yellow]")
            return []
        
        table = Table(title="Categories (Collections)", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=10)
        table.add_column("Title", style="green", width=30)
        table.add_column("Handle", style="blue", width=20)
        table.add_column("Products", style="yellow", width=10)
        table.add_column("Published", style="magenta", width=10)
        
        for collection in self._cached_collections:
            table.add_row(
                str(collection.get("id", "")),
                collection.get("title", "N/A"),
                collection.get("handle", "N/A"),
                str(collection.get("products_count", 0)),
                "Yes" if collection.get("published", False) else "No"
            )
        
        console.print(table)
        return self._cached_collections
    
    def get_category_by_id(self, category_id: str) -> Optional[Dict]:
        """Get category by ID"""
        if self._cached_collections:
            for collection in self._cached_collections:
                if str(collection.get("id")) == str(category_id):
                    return collection
        
        # Fetch from API if not in cache
        return self.client.get_collection(category_id)
    
    def select_category(self) -> Optional[str]:
        """Interactive category selection"""
        collections = self.list_categories()
        
        if not collections:
            return None
        
        console.print("\n[cyan]Select a category:[/cyan]")
        for idx, collection in enumerate(collections, 1):
            console.print(f"  {idx}. {collection.get('title')} (ID: {collection.get('id')})")
        
        try:
            choice = console.input("\n[yellow]Enter category number: [/yellow]")
            idx = int(choice) - 1
            if 0 <= idx < len(collections):
                selected = collections[idx]
                console.print(f"[green]✅ Selected: {selected.get('title')}[/green]")
                return str(selected.get("id"))
            else:
                console.print("[red]❌ Invalid selection.[/red]")
                return None
        except ValueError:
            console.print("[red]❌ Invalid input.[/red]")
            return None
    
    def create_category(self, title: str, description: str = "", published: bool = True):
        """Create a new category (collection)"""
        # Generate handle from title
        handle = title.lower().replace(" ", "-").replace("_", "-")
        handle = "".join(c for c in handle if c.isalnum() or c == "-")
        
        collection_data = {
            "title": title,
            "body_html": description,
            "published": published,
            "handle": handle
        }
        
        console.print("[cyan]🏷️  Creating category...[/cyan]")
        collection = self.client.create_collection(collection_data)
        
        if collection:
            console.print(f"[green]✅ Category '{title}' created successfully![/green]")
            console.print(f"[green]Category ID: {collection.get('id')}[/green]")
            # Refresh cache
            self._cached_collections = None
            return collection
        else:
            console.print("[red]❌ Failed to create category.[/red]")
            return None
    
    def show_category_details(self, category_id: str):
        """Show detailed information about a category"""
        console.print(f"[cyan]🏷️  Fetching category {category_id}...[/cyan]")
        collection = self.client.get_collection(category_id)
        
        if not collection:
            console.print("[red]❌ Category not found.[/red]")
            return
        
        details = f"""
[bold]Title:[/bold] {collection.get('title', 'N/A')}
[bold]Handle:[/bold] {collection.get('handle', 'N/A')}
[bold]Published:[/bold] {'Yes' if collection.get('published', False) else 'No'}
[bold]Products Count:[/bold] {collection.get('products_count', 0)}
[bold]Description:[/bold] {collection.get('body_html', 'N/A')[:200]}...
[bold]Created:[/bold] {collection.get('created_at', 'N/A')}
[bold]Updated:[/bold] {collection.get('updated_at', 'N/A')}
"""
        
        console.print(Panel(details, title="Category Details", border_style="green"))

