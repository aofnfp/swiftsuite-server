"""
Main CLI Interface
Terminal-based Shopify Inventory Management System
"""

import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich import box

from user_manager import UserManager
from shopify_client import ShopifyClient
from product_manager import ProductManager
from category_manager import CategoryManager
from order_manager import OrderManager
from inventory_manager import InventoryManager
from onboarding import Onboarding

console = Console()


class InventorySystem:
    """Main inventory management system"""
    
    def __init__(self):
        """Initialize the system"""
        self.user_manager = UserManager()
        self.current_user = None
        self.current_client = None
        self.product_manager = None
        self.category_manager = None
        self.order_manager = None
        self.inventory_manager = None
    
    def select_user(self):
        """Select a user account"""
        users = self.user_manager.list_users()
        
        if not users:
            console.print("[yellow]No users found. Let's set up your first account![/yellow]\n")
            onboarding = Onboarding(self.user_manager)
            if onboarding.run():
                users = self.user_manager.list_users()
            else:
                return False
        
        if len(users) == 1:
            # Auto-select if only one user
            self.current_user = users[0]
        else:
            # Show user selection
            console.print("\n[bold cyan]Select an account:[/bold cyan]\n")
            table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
            table.add_column("#", style="cyan", width=5)
            table.add_column("Name", style="green", width=20)
            table.add_column("Store URL", style="blue", width=30)
            
            for idx, user in enumerate(users, 1):
                masked_url = user["store_url"][:20] + "..." if len(user["store_url"]) > 20 else user["store_url"]
                table.add_row(str(idx), user["name"], masked_url)
            
            console.print(table)
            
            try:
                choice = IntPrompt.ask("\n[yellow]Enter account number[/yellow]", default=1)
                if 1 <= choice <= len(users):
                    self.current_user = users[choice - 1]
                else:
                    console.print("[red]❌ Invalid selection.[/red]")
                    return False
            except KeyboardInterrupt:
                return False
        
        # Initialize client and managers
        if self.current_user:
            self.current_client = ShopifyClient(
                self.current_user["store_url"],
                self.current_user["access_token"]
            )
            self.product_manager = ProductManager(self.current_client)
            self.category_manager = CategoryManager(self.current_client)
            self.order_manager = OrderManager(self.current_client)
            self.inventory_manager = InventoryManager(self.current_client)
            
            # Test connection
            if not self.current_client.test_connection():
                console.print("[red]❌ Failed to connect to store. Please check your credentials.[/red]")
                return False
            
            shop_info = self.current_client.get_shop_info()
            store_name = shop_info.get("name", self.current_user["store_url"]) if shop_info else self.current_user["store_url"]
            console.print(f"\n[green]✅ Connected to: {store_name}[/green]\n")
            return True
        
        return False
    
    def show_main_menu(self):
        """Display main menu"""
        menu_text = """
[bold cyan]Main Menu[/bold cyan]

[1] 📦 Products
[2] 🏷️  Categories
[3] 📋 Orders
[4] 📊 Inventory
[5] 👥 Manage Accounts
[6] 🔄 Switch Account
[7] ℹ️  Store Info
[0] 🚪 Exit
"""
        console.print(Panel(menu_text, title="Inventory Management System", border_style="cyan"))
    
    def products_menu(self):
        """Products submenu"""
        while True:
            menu_text = """
[bold cyan]Product Management[/bold cyan]

[1] List Products
[2] View Product Details
[3] Create Product
[4] Update Product
[5] Delete Product
[0] Back to Main Menu
"""
            console.print(Panel(menu_text, border_style="green"))
            
            choice = Prompt.ask("\n[yellow]Select an option[/yellow]", choices=["0", "1", "2", "3", "4", "5"], default="0")
            
            if choice == "0":
                break
            elif choice == "1":
                limit = IntPrompt.ask("How many products to show", default=50)
                self.product_manager.list_products(limit=limit, page_info=None)
            elif choice == "2":
                product_id = Prompt.ask("Enter product ID")
                self.product_manager.show_product_details(product_id)
            elif choice == "3":
                self._create_product_interactive()
            elif choice == "4":
                self._update_product_interactive()
            elif choice == "5":
                product_id = Prompt.ask("Enter product ID to delete")
                self.product_manager.delete_product(product_id)
            
            if choice != "0":
                console.input("\n[dim]Press Enter to continue...[/dim]")
    
    def _create_product_interactive(self):
        """Interactive product creation with all features"""
        console.print("\n[bold cyan]Create New Product[/bold cyan]\n")
        
        # Basic Information
        title = Prompt.ask("[yellow]Product Title[/yellow]")
        description = Prompt.ask("[yellow]Description (optional)[/yellow]", default="")
        product_type = Prompt.ask("[yellow]Product Type (optional)[/yellow]", default="")
        vendor = Prompt.ask("[yellow]Vendor (optional)[/yellow]", default="")
        handle = Prompt.ask("[yellow]Handle/URL slug (optional, auto-generated if empty)[/yellow]", default="")
        
        # Tags
        tags = Prompt.ask("[yellow]Tags (comma-separated, optional)[/yellow]", default="")
        
        # Pricing and Inventory
        price = Prompt.ask("[yellow]Price[/yellow]", default="0.00")
        sku = Prompt.ask("[yellow]SKU (optional)[/yellow]", default="")
        inventory = IntPrompt.ask("[yellow]Initial Inventory Quantity[/yellow]", default=0)
        
        # Images
        images = []
        add_images = Confirm.ask("[yellow]Add product images?[/yellow]", default=False)
        if add_images:
            console.print("[dim]Enter image URLs (one per line, press Enter twice when done):[/dim]")
            while True:
                img_url = console.input("[cyan]Image URL (or press Enter to finish): [/cyan]")
                if not img_url.strip():
                    break
                images.append(img_url.strip())
        
        # Variants/Attributes
        has_variants = Confirm.ask("[yellow]Does this product have variants (Size, Color, etc.)?[/yellow]", default=False)
        options = None
        variants_list = None
        
        if has_variants:
            console.print("\n[yellow]Set up product options (e.g., Size, Color):[/yellow]")
            options = []
            num_options = IntPrompt.ask("[cyan]How many options? (e.g., Size and Color = 2)[/cyan]", default=1)
            
            for i in range(num_options):
                option_name = Prompt.ask(f"[cyan]Option {i+1} name (e.g., Size, Color)[/cyan]")
                option_values_str = Prompt.ask(f"[cyan]Option {i+1} values (comma-separated, e.g., Small,Medium,Large)[/cyan]")
                option_values = [v.strip() for v in option_values_str.split(",")]
                options.append({"name": option_name, "values": option_values})
            
            # Create variants from options
            console.print("\n[yellow]Creating variants from options...[/yellow]")
            variants_list = []
            # For simplicity, create one variant per combination
            # In a full implementation, you'd generate all combinations
            for i, option in enumerate(options):
                for value in option["values"]:
                    variant_price = Prompt.ask(f"[cyan]Price for {option['name']}={value}[/cyan]", default=price)
                    variant_sku = Prompt.ask(f"[cyan]SKU for {option['name']}={value} (optional)[/cyan]", default="")
                    variant_inventory = IntPrompt.ask(f"[cyan]Inventory for {option['name']}={value}[/cyan]", default=inventory)
                    
                    variant_data = {
                        "price": variant_price,
                        "inventory_quantity": variant_inventory,
                        "option1": value
                    }
                    if variant_sku:
                        variant_data["sku"] = variant_sku
                    variants_list.append(variant_data)
        
        # Category/Collection
        use_category = Confirm.ask("[yellow]Assign to a category/collection?[/yellow]", default=False)
        collection_id = None
        if use_category:
            create_new = Confirm.ask("[yellow]Create new category?[/yellow]", default=False)
            if create_new:
                cat_title = Prompt.ask("[cyan]Category name[/cyan]")
                cat_description = Prompt.ask("[cyan]Category description (optional)[/cyan]", default="")
                collection = self.category_manager.create_category(cat_title, cat_description)
                if collection:
                    collection_id = str(collection.get("id"))
            else:
                collection_id = self.category_manager.select_category()
        
        # SEO
        seo_title = Prompt.ask("[yellow]SEO Title (optional)[/yellow]", default="")
        seo_description = Prompt.ask("[yellow]SEO Description (optional)[/yellow]", default="")
        
        # Create product
        self.product_manager.create_product(
            title=title,
            description=description,
            product_type=product_type,
            vendor=vendor,
            price=price,
            sku=sku,
            inventory_quantity=inventory,
            collection_id=collection_id,
            tags=tags,
            images=images if images else None,
            handle=handle,
            options=options,
            variants=variants_list,
            seo_title=seo_title,
            seo_description=seo_description
        )
    
    def _update_product_interactive(self):
        """Interactive product update with all fields"""
        console.print("\n[bold cyan]Update Product[/bold cyan]\n")
        product_id = Prompt.ask("[yellow]Product ID[/yellow]")
        
        updates = {}
        
        # Basic fields
        if Confirm.ask("Update title?", default=False):
            updates["title"] = Prompt.ask("New title")
        if Confirm.ask("Update description?", default=False):
            updates["description"] = Prompt.ask("New description")
        if Confirm.ask("Update product type?", default=False):
            updates["product_type"] = Prompt.ask("New product type")
        if Confirm.ask("Update vendor?", default=False):
            updates["vendor"] = Prompt.ask("New vendor")
        if Confirm.ask("Update handle/URL?", default=False):
            updates["handle"] = Prompt.ask("New handle")
        if Confirm.ask("Update status?", default=False):
            status = Prompt.ask("Status", choices=["active", "archived", "draft"], default="active")
            updates["status"] = status
        
        # Tags
        if Confirm.ask("Update tags?", default=False):
            updates["tags"] = Prompt.ask("New tags (comma-separated)")
        
        # Images
        if Confirm.ask("Update images?", default=False):
            images = []
            console.print("[dim]Enter image URLs (one per line, press Enter twice when done):[/dim]")
            while True:
                img_url = console.input("[cyan]Image URL (or press Enter to finish): [/cyan]")
                if not img_url.strip():
                    break
                images.append(img_url.strip())
            if images:
                updates["images"] = images
        
        # SEO
        if Confirm.ask("Update SEO title?", default=False):
            updates["seo_title"] = Prompt.ask("New SEO title")
        if Confirm.ask("Update SEO description?", default=False):
            updates["seo_description"] = Prompt.ask("New SEO description")
        
        if updates:
            self.product_manager.update_product(product_id, **updates)
        else:
            console.print("[yellow]No updates specified.[/yellow]")
    
    def categories_menu(self):
        """Categories submenu"""
        while True:
            menu_text = """
[bold cyan]Category Management[/bold cyan]

[1] List Categories
[2] View Category Details
[3] Create Category
[4] Select Category (for product assignment)
[0] Back to Main Menu
"""
            console.print(Panel(menu_text, border_style="blue"))
            
            choice = Prompt.ask("\n[yellow]Select an option[/yellow]", choices=["0", "1", "2", "3", "4"], default="0")
            
            if choice == "0":
                break
            elif choice == "1":
                self.category_manager.list_categories(refresh=True)
            elif choice == "2":
                category_id = Prompt.ask("Enter category ID")
                self.category_manager.show_category_details(category_id)
            elif choice == "3":
                self._create_category_interactive()
            elif choice == "4":
                selected = self.category_manager.select_category()
                if selected:
                    console.print(f"[green]Selected category ID: {selected}[/green]")
            
            if choice != "0":
                console.input("\n[dim]Press Enter to continue...[/dim]")
    
    def _create_category_interactive(self):
        """Interactive category creation"""
        console.print("\n[bold cyan]Create New Category[/bold cyan]\n")
        title = Prompt.ask("[yellow]Category Title[/yellow]")
        description = Prompt.ask("[yellow]Description (optional)[/yellow]", default="")
        published = Confirm.ask("[yellow]Publish immediately?[/yellow]", default=True)
        
        self.category_manager.create_category(
            title=title,
            description=description,
            published=published
        )
    
    def orders_menu(self):
        """Orders submenu"""
        while True:
            menu_text = """
[bold cyan]Order Management[/bold cyan]

[1] List Orders
[2] View Order Details
[3] Track Order
[4] Update Order
[0] Back to Main Menu
"""
            console.print(Panel(menu_text, border_style="magenta"))
            
            choice = Prompt.ask("\n[yellow]Select an option[/yellow]", choices=["0", "1", "2", "3", "4"], default="0")
            
            if choice == "0":
                break
            elif choice == "1":
                status = Prompt.ask(
                    "[yellow]Filter by status (optional)[/yellow]",
                    choices=["", "open", "closed", "cancelled", "any"],
                    default=""
                )
                status = None if not status else status
                limit = IntPrompt.ask("How many orders to show", default=50)
                self.order_manager.list_orders(limit=limit, status=status)
            elif choice == "2":
                order_id = Prompt.ask("Enter order ID")
                self.order_manager.show_order_details(order_id)
            elif choice == "3":
                order_id = Prompt.ask("Enter order ID")
                self.order_manager.track_order(order_id)
            elif choice == "4":
                self._update_order_interactive()
            
            if choice != "0":
                console.input("\n[dim]Press Enter to continue...[/dim]")
    
    def _update_order_interactive(self):
        """Interactive order update"""
        console.print("\n[bold cyan]Update Order[/bold cyan]\n")
        order_id = Prompt.ask("[yellow]Order ID[/yellow]")
        
        updates = {}
        if Confirm.ask("Update note?", default=False):
            updates["note"] = Prompt.ask("New note")
        if Confirm.ask("Update tags?", default=False):
            updates["tags"] = Prompt.ask("New tags (comma-separated)")
        if Confirm.ask("Update financial status?", default=False):
            status = Prompt.ask(
                "Financial status",
                choices=["pending", "authorized", "partially_paid", "paid", "partially_refunded", "refunded", "voided"],
                default="pending"
            )
            updates["financial_status"] = status
        
        if updates:
            self.order_manager.update_order(order_id, **updates)
        else:
            console.print("[yellow]No updates specified.[/yellow]")
    
    def inventory_menu(self):
        """Inventory management menu"""
        while True:
            menu_text = """
[bold cyan]Inventory Management[/bold cyan]

[1] List Inventory Levels
[2] List Store Locations
[3] View Location Details
[0] Back to Main Menu
"""
            console.print(Panel(menu_text, border_style="cyan"))
            
            choice = Prompt.ask("\n[yellow]Select an option[/yellow]", choices=["0", "1", "2", "3"], default="0")
            
            if choice == "0":
                break
            elif choice == "1":
                self.inventory_manager.list_inventory_levels()
            elif choice == "2":
                self.inventory_manager.list_locations()
            elif choice == "3":
                location_id = Prompt.ask("Enter location ID")
                self.inventory_manager.show_location_details(location_id)
            
            if choice != "0":
                console.input("\n[dim]Press Enter to continue...[/dim]")
    
    def accounts_menu(self):
        """Account management menu"""
        while True:
            menu_text = """
[bold cyan]Account Management[/bold cyan]

[1] List Accounts
[2] Add New Account
[3] Delete Account
[0] Back to Main Menu
"""
            console.print(Panel(menu_text, border_style="yellow"))
            
            choice = Prompt.ask("\n[yellow]Select an option[/yellow]", choices=["0", "1", "2", "3"], default="0")
            
            if choice == "0":
                break
            elif choice == "1":
                self.user_manager.display_users()
            elif choice == "2":
                onboarding = Onboarding(self.user_manager)
                onboarding.run()
            elif choice == "3":
                self.user_manager.display_users()
                user_id = Prompt.ask("\n[yellow]Enter user ID to delete[/yellow]")
                if Confirm.ask("[red]Are you sure?[/red]", default=False):
                    self.user_manager.delete_user(user_id)
            
            if choice != "0":
                console.input("\n[dim]Press Enter to continue...[/dim]")
    
    def show_store_info(self):
        """Show store information"""
        if not self.current_client:
            console.print("[red]No active connection.[/red]")
            return
        
        shop_info = self.current_client.get_shop_info()
        if shop_info:
            info_text = f"""
[bold]Store Name:[/bold] {shop_info.get('name', 'N/A')}
[bold]Domain:[/bold] {shop_info.get('domain', 'N/A')}
[bold]Email:[/bold] {shop_info.get('email', 'N/A')}
[bold]Currency:[/bold] {shop_info.get('currency', 'N/A')}
[bold]Timezone:[/bold] {shop_info.get('timezone', 'N/A')}
[bold]Plan:[/bold] {shop_info.get('plan_name', 'N/A')}
"""
            console.print(Panel(info_text, title="Store Information", border_style="cyan"))
        else:
            console.print("[red]Failed to fetch store information.[/red]")
    
    def run(self):
        """Run the main application loop"""
        console.print(Panel.fit(
            "[bold cyan]Shopify Inventory Management System[/bold cyan]\n[dim]Terminal-based inventory management[/dim]",
            border_style="green"
        ))
        
        # Select or create user
        if not self.select_user():
            console.print("[yellow]Exiting...[/yellow]")
            return
        
        # Main loop
        while True:
            try:
                self.show_main_menu()
                choice = Prompt.ask("\n[yellow]Select an option[/yellow]", choices=["0", "1", "2", "3", "4", "5", "6", "7"], default="0")
                
                if choice == "0":
                    console.print("\n[green]Thank you for using Shopify Inventory Management System![/green]")
                    break
                elif choice == "1":
                    self.products_menu()
                elif choice == "2":
                    self.categories_menu()
                elif choice == "3":
                    self.orders_menu()
                elif choice == "4":
                    self.inventory_menu()
                elif choice == "5":
                    self.accounts_menu()
                elif choice == "6":
                    if not self.select_user():
                        break
                elif choice == "7":
                    self.show_store_info()
                    console.input("\n[dim]Press Enter to continue...[/dim]")
            
            except KeyboardInterrupt:
                console.print("\n\n[yellow]Exiting...[/yellow]")
                break
            except Exception as e:
                console.print(f"\n[red]❌ Error: {e}[/red]")
                console.input("\n[dim]Press Enter to continue...[/dim]")


def main():
    """Entry point"""
    try:
        system = InventorySystem()
        system.run()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Goodbye![/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Fatal Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()

