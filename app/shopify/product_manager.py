"""
Product Management Module
Handles product operations (CRUD)
"""

from typing import Dict, List, Optional, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from shopify_client import ShopifyClient

console = Console()


class ProductManager:
    """Manages product operations"""
    
    def __init__(self, client: ShopifyClient):
        """Initialize product manager with Shopify client"""
        self.client = client
    
    def list_products(self, limit: int = 50, page_info: Optional[str] = None):
        """List all products"""
        console.print("[cyan]📦 Fetching products...[/cyan]")
        products, next_page = self.client.get_products(limit=limit, page_info=page_info)
        
        if products is None:
            # Error occurred, message already displayed
            return []
        
        if not products:
            console.print("[yellow]No products found in your store.[/yellow]")
            console.print("[dim]This could mean:[/dim]")
            console.print("[dim]  • You haven't created any products yet[/dim]")
            console.print("[dim]  • Products are in draft/archived status[/dim]")
            console.print("[dim]  • There was an error fetching products (check error messages above)[/dim]")
            return []
        
        table = Table(title=f"Products ({len(products)} found)", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=10)
        table.add_column("Title", style="green", width=30)
        table.add_column("Type", style="blue", width=20)
        table.add_column("Status", style="yellow", width=10)
        table.add_column("Price", style="magenta", width=12)
        table.add_column("Inventory", style="red", width=10)
        table.add_column("Tags", style="cyan", width=20)
        table.add_column("Images", style="blue", width=8)
        
        for product in products:
            variant = product.get("variants", [{}])[0] if product.get("variants") else {}
            price = variant.get("price", "N/A")
            inventory = variant.get("inventory_quantity", "N/A")
            tags = product.get("tags", "")[:20] if product.get("tags") else "None"
            images_count = len(product.get("images", []))
            
            table.add_row(
                str(product.get("id", "")),
                product.get("title", "N/A")[:30],
                product.get("product_type", "N/A")[:20],
                product.get("status", "N/A"),
                f"${price}" if price != "N/A" else "N/A",
                str(inventory) if inventory != "N/A" else "N/A",
                tags,
                str(images_count) if images_count > 0 else "0"
            )
        
        console.print(table)
        return products
    
    def show_product_details(self, product_id: str):
        """Show detailed information about a product"""
        console.print(f"[cyan]📦 Fetching product {product_id}...[/cyan]")
        product = self.client.get_product(product_id)
        
        if not product:
            console.print("[red]❌ Product not found.[/red]")
            return
        
        # Display product details
        tags = product.get('tags', 'None')
        handle = product.get('handle', 'N/A')
        seo_title = product.get('metafields_global_title_tag', 'N/A')
        seo_description = product.get('metafields_global_description_tag', 'N/A')
        
        details = f"""
[bold]Title:[/bold] {product.get('title', 'N/A')}
[bold]Handle:[/bold] {handle}
[bold]Type:[/bold] {product.get('product_type', 'N/A')}
[bold]Status:[/bold] {product.get('status', 'N/A')}
[bold]Vendor:[/bold] {product.get('vendor', 'N/A')}
[bold]Tags:[/bold] {tags}
[bold]Created:[/bold] {product.get('created_at', 'N/A')[:19] if product.get('created_at') else 'N/A'}
[bold]Updated:[/bold] {product.get('updated_at', 'N/A')[:19] if product.get('updated_at') else 'N/A'}
[bold]Description:[/bold] {product.get('body_html', 'N/A')[:200]}...
"""
        
        console.print(Panel(details, title="Product Details", border_style="green"))
        
        # Show images
        images = product.get("images", [])
        if images:
            console.print("\n[bold cyan]Product Images:[/bold cyan]")
            for idx, image in enumerate(images, 1):
                image_url = image.get("src", "N/A")
                console.print(f"  {idx}. {image_url[:80]}...")
        
        # Show variants
        variants = product.get("variants", [])
        if variants:
            variant_table = Table(title="Variants", show_header=True, header_style="bold cyan")
            variant_table.add_column("ID", style="cyan")
            variant_table.add_column("Title", style="green")
            variant_table.add_column("Price", style="magenta")
            variant_table.add_column("SKU", style="blue")
            variant_table.add_column("Inventory", style="red")
            
            for variant in variants:
                variant_table.add_row(
                    str(variant.get("id", "")),
                    variant.get("title", "N/A"),
                    f"${variant.get('price', 'N/A')}",
                    variant.get("sku", "N/A") or "N/A",
                    str(variant.get("inventory_quantity", "N/A"))
                )
            
            console.print(variant_table)
    
    def create_product(self, title: str, description: str = "", product_type: str = "", 
                      vendor: str = "", price: str = "", sku: str = "", 
                      inventory_quantity: int = 0, collection_id: Optional[str] = None,
                      tags: str = "", images: List[str] = None, handle: str = "",
                      options: List[Dict] = None, variants: List[Dict] = None,
                      seo_title: str = "", seo_description: str = ""):
        """Create a new product with full support for images, tags, attributes, etc."""
        product_data = {
            "title": title,
            "body_html": description,
            "product_type": product_type,
            "vendor": vendor,
        }
        
        # Add tags
        if tags:
            product_data["tags"] = tags
        
        # Add handle (URL slug)
        if handle:
            product_data["handle"] = handle
        
        # Add SEO fields (using metafields API - these need to be set after product creation)
        # Note: SEO fields are typically handled via metafields, not directly in product creation
        # We'll handle this after product creation if needed
        
        # Add images
        if images:
            product_data["images"] = [{"src": img_url} for img_url in images]
        
        # Add variants - ensure proper structure
        if variants:
            # Validate and clean variants
            cleaned_variants = []
            for variant in variants:
                cleaned_variant = {}
                if "price" in variant:
                    cleaned_variant["price"] = str(variant["price"])
                if "sku" in variant and variant["sku"]:
                    cleaned_variant["sku"] = variant["sku"]
                if "inventory_quantity" in variant:
                    cleaned_variant["inventory_quantity"] = int(variant["inventory_quantity"])
                # Add option values if present
                for key in ["option1", "option2", "option3"]:
                    if key in variant:
                        cleaned_variant[key] = variant[key]
                cleaned_variants.append(cleaned_variant)
            product_data["variants"] = cleaned_variants
        else:
            # Default variant - ensure price is a string
            variant_data = {
                "price": str(price) if price else "0.00"
            }
            if sku:
                variant_data["sku"] = sku
            if inventory_quantity:
                variant_data["inventory_quantity"] = int(inventory_quantity)
            product_data["variants"] = [variant_data]
        
        # Add options (for variants like Size, Color, etc.)
        if options:
            product_data["options"] = options
        
        console.print("[cyan]📦 Creating product...[/cyan]")
        product = self.client.create_product(product_data)
        
        # Add to collection after creation (collections can't be set during creation)
        if product and collection_id:
            if self.client.add_product_to_collection(str(product.get("id")), collection_id):
                console.print("[green]✅ Product added to collection![/green]")
            else:
                console.print("[yellow]⚠️  Product created but failed to add to collection.[/yellow]")
        
        if product:
            console.print(f"[green]✅ Product '{title}' created successfully![/green]")
            console.print(f"[green]Product ID: {product.get('id')}[/green]")
            return product
        else:
            console.print("[red]❌ Failed to create product.[/red]")
            return None
    
    def update_product(self, product_id: str, **kwargs):
        """Update a product with support for all fields"""
        product_data = {}
        
        if "title" in kwargs:
            product_data["title"] = kwargs["title"]
        if "description" in kwargs:
            product_data["body_html"] = kwargs["description"]
        if "product_type" in kwargs:
            product_data["product_type"] = kwargs["product_type"]
        if "vendor" in kwargs:
            product_data["vendor"] = kwargs["vendor"]
        if "status" in kwargs:
            product_data["status"] = kwargs["status"]
        if "tags" in kwargs:
            product_data["tags"] = kwargs["tags"]
        if "handle" in kwargs:
            product_data["handle"] = kwargs["handle"]
        if "images" in kwargs:
            product_data["images"] = [{"src": img} for img in kwargs["images"]]
        if "variants" in kwargs:
            product_data["variants"] = kwargs["variants"]
        if "options" in kwargs:
            product_data["options"] = kwargs["options"]
        if "seo_title" in kwargs:
            product_data["metafields_global_title_tag"] = kwargs["seo_title"]
        if "seo_description" in kwargs:
            product_data["metafields_global_description_tag"] = kwargs["seo_description"]
        
        if not product_data:
            console.print("[yellow]⚠️  No fields to update.[/yellow]")
            return None
        
        console.print(f"[cyan]📦 Updating product {product_id}...[/cyan]")
        product = self.client.update_product(product_id, product_data)
        
        if product:
            console.print(f"[green]✅ Product updated successfully![/green]")
            return product
        else:
            console.print("[red]❌ Failed to update product.[/red]")
            return None
    
    def delete_product(self, product_id: str):
        """Delete a product"""
        console.print(f"[yellow]⚠️  Deleting product {product_id}...[/yellow]")
        
        # Confirm deletion
        confirm = console.input("[yellow]Are you sure? (yes/no): [/yellow]")
        if confirm.lower() != "yes":
            console.print("[yellow]Deletion cancelled.[/yellow]")
            return False
        
        success = self.client.delete_product(product_id)
        
        if success:
            console.print(f"[green]✅ Product {product_id} deleted successfully![/green]")
            return True
        else:
            console.print("[red]❌ Failed to delete product.[/red]")
            return False

