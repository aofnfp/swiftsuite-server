"""
Setup Helper Script
Helps users create Shopify apps and get access tokens from the terminal
"""

import webbrowser
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from shopify_client import ShopifyClient

console = Console()


def open_app_creation_page(store_url: str):
    """Open the app creation page in browser"""
    # Clean store URL
    store_url = store_url.replace('https://', '').replace('http://', '').replace('/', '')
    if not store_url.endswith('.myshopify.com'):
        if '.' not in store_url:
            store_url = f"{store_url}.myshopify.com"
    
    admin_url = f"https://{store_url}/admin/apps/development"
    console.print(f"\n[green]Opening Shopify Admin in your browser...[/green]")
    console.print(f"[dim]URL: {admin_url}[/dim]\n")
    
    try:
        webbrowser.open(admin_url)
        console.print("[green]✅ Browser opened![/green]")
        return True
    except Exception as e:
        console.print(f"[yellow]⚠️  Could not open browser: {e}[/yellow]")
        console.print(f"[cyan]Please manually visit: {admin_url}[/cyan]")
        return False


def guide_app_creation():
    """Guide user through app creation process"""
    guide = """
[bold cyan]Step-by-Step App Creation Guide[/bold cyan]

[bold]Step 1:[/bold] Create the App
  • In the browser, click [cyan]"Create an app"[/cyan]
  • Name it: [green]"Inventory Manager"[/green] (or any name you prefer)
  • Click [cyan]"Create app"[/cyan]

[bold]Step 2:[/bold] Configure API Scopes
  • Click [cyan]"Configure Admin API scopes"[/cyan]
  • Enable these scopes:
    ✅ read_products
    ✅ write_products
    ✅ read_orders
    ✅ write_orders
    ✅ read_inventory
    ✅ write_inventory
  • Click [cyan]"Save"[/cyan]

[bold]Step 3:[/bold] Install the App
  • Click [cyan]"Install app"[/cyan] button
  • Confirm installation

[bold]Step 4:[/bold] Get Your Access Token
  • You'll see [yellow]"Admin API access token"[/yellow]
  • Click [cyan]"Reveal token once"[/cyan] or [cyan]"Show token"[/cyan]
  • [red]⚠️  Copy it immediately - you won't see it again![/red]
"""
    console.print(Panel(guide, title="App Creation Instructions", border_style="cyan"))


def validate_token(store_url: str, token: str) -> bool:
    """Validate the access token by testing connection"""
    console.print("\n[cyan]🔍 Validating your access token...[/cyan]")
    
    try:
        client = ShopifyClient(store_url, token)
        if client.test_connection():
            shop_info = client.get_shop_info()
            if shop_info:
                console.print(f"[green]✅ Token is valid![/green]")
                console.print(f"[green]Connected to: {shop_info.get('name', store_url)}[/green]")
                return True
            else:
                console.print("[green]✅ Token is valid![/green]")
                return True
        else:
            console.print("[red]❌ Token validation failed.[/red]")
            console.print("[yellow]Please check that:[/yellow]")
            console.print("  • The token was copied correctly")
            console.print("  • The app is installed")
            console.print("  • The correct scopes are enabled")
            return False
    except Exception as e:
        console.print(f"[red]❌ Error validating token: {e}[/red]")
        return False


def interactive_setup():
    """Interactive setup process"""
    console.print(Panel.fit(
        "[bold cyan]Shopify App Setup Helper[/bold cyan]\n[dim]Automated app creation assistant[/dim]",
        border_style="green"
    ))
    
    # Get store URL
    console.print("\n[bold cyan]Let's set up your Shopify app![/bold cyan]\n")
    store_url = Prompt.ask("[cyan]Enter your Shopify store URL[/cyan]")
    console.print("[dim]Example: yourstore.myshopify.com or just 'yourstore'[/dim]")
    
    # Clean store URL
    store_url = store_url.strip().lower()
    if not store_url.endswith('.myshopify.com'):
        if '.' not in store_url:
            store_url = f"{store_url}.myshopify.com"
    
    # Open browser
    console.print("\n[yellow]I'll open your Shopify Admin in the browser...[/yellow]")
    open_browser = Confirm.ask("[cyan]Open browser now?[/cyan]", default=True)
    
    if open_browser:
        open_app_creation_page(store_url)
    
    # Show guide
    guide_app_creation()
    
    # Wait for user to create app
    console.print("\n[yellow]⏳ Take your time to create the app in the browser.[/yellow]")
    console.print("[yellow]When you're done, come back here and we'll validate your token.[/yellow]\n")
    
    ready = Confirm.ask("[cyan]Have you created the app and copied the access token?[/cyan]", default=False)
    
    if not ready:
        console.print("\n[yellow]No problem! Run this script again when you're ready.[/yellow]")
        return None, None
    
    # Get token
    console.print("\n[bold cyan]Enter your access token:[/bold cyan]")
    token = Prompt.ask("[cyan]Paste your Admin API access token[/cyan]", password=True)
    
    # Validate token
    if validate_token(store_url, token):
        console.print("\n[bold green]🎉 Success! Your token is valid![/bold green]")
        console.print("\n[yellow]Next steps:[/yellow]")
        console.print("  1. Run [cyan]python main.py[/cyan]")
        console.print("  2. Choose option 1 (Custom App)")
        console.print("  3. Paste this token when prompted")
        console.print(f"  4. Your store URL: [cyan]{store_url}[/cyan]")
        
        # Option to save directly
        save_now = Confirm.ask("\n[yellow]Would you like to save this directly to the app now?[/yellow]", default=True)
        if save_now:
            return store_url, token
    else:
        console.print("\n[red]❌ Token validation failed. Please try again.[/red]")
        retry = Confirm.ask("[yellow]Would you like to try again?[/yellow]", default=True)
        if retry:
            return interactive_setup()
    
    return None, None


def save_to_app(store_url: str, token: str, name: str = None):
    """Save credentials directly to the application"""
    from user_manager import UserManager
    
    if not name:
        name = Prompt.ask("[cyan]Enter a name for this account[/cyan]", default="My Store")
    
    user_manager = UserManager()
    user_id = user_manager.add_user(name, store_url, token)
    
    if user_id:
        console.print(f"\n[bold green]✅ Account '{name}' saved successfully![/bold green]")
        console.print("\n[green]You can now run [cyan]python main.py[/cyan] and start using the system![/green]")
        return True
    else:
        console.print("\n[red]❌ Failed to save account.[/red]")
        return False


def main():
    """Main entry point"""
    try:
        store_url, token = interactive_setup()
        
        if store_url and token:
            save_to_app(store_url, token)
        
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Setup cancelled.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()

