"""
Smart Onboarding Module
Guides new users through the setup process
"""

from typing import Optional
import webbrowser
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from user_manager import UserManager
from shopify_client import ShopifyClient
from shopify_oauth import ShopifyOAuth

console = Console()


class Onboarding:
    """Handles smart onboarding for new users"""
    
    def __init__(self, user_manager: UserManager):
        """Initialize onboarding with user manager"""
        self.user_manager = user_manager
    
    def welcome_screen(self):
        """Display welcome screen"""
        welcome_text = """
[bold cyan]Welcome to Shopify Inventory Management System![/bold cyan]

This system allows you to manage your Shopify store inventory from the terminal.
You can:
  • Manage products (create, update, delete, list)
  • Organize categories/collections
  • Track and manage orders
  • Monitor inventory levels
  • Support multiple Shopify accounts

Let's get started by adding your Shopify store credentials.
"""
        console.print(Panel(welcome_text, title="Welcome", border_style="green"))
    
    def guide_api_setup(self, oauth_mode: bool = False):
        """Guide user through API token setup"""
        if oauth_mode:
            guide_text = """
[bold]OAuth Setup Instructions:[/bold]

1. You'll be provided with an authorization URL
2. Open that URL in your web browser
3. Log in to your Shopify Admin if prompted
4. Review and approve the requested permissions
5. After approval, you'll see an authorization code
6. Copy that code and paste it here

[yellow]⚠️  Keep your client ID and secret secure![/yellow]
"""
        else:
            guide_text = """
[bold]How to get your Shopify API Token:[/bold]

1. Log in to your Shopify Admin panel
2. Go to [cyan]Apps[/cyan] → [cyan]Develop apps[/cyan]
3. Click [cyan]Create an app[/cyan]
4. Give your app a name (e.g., "Inventory Manager")
5. Configure Admin API scopes:
   • [green]read_products[/green] and [green]write_products[/green]
   • [green]read_orders[/green] and [green]write_orders[/green]
   • [green]read_inventory[/green] and [green]write_inventory[/green]
6. Click [cyan]Save[/cyan] and then [cyan]Install app[/cyan]
7. Copy the [yellow]Admin API access token[/yellow]

[yellow]⚠️  Keep your API token secure! Never share it publicly.[/yellow]
"""
        console.print(Panel(guide_text, title="API Setup Guide", border_style="yellow"))
    
    def collect_user_info(self) -> tuple:
        """Collect user information interactively"""
        console.print("\n[bold cyan]Let's set up your Shopify account:[/bold cyan]\n")
        
        # Get user name
        name = Prompt.ask("[cyan]Enter a name for this account[/cyan]", default="My Store")
        
        # Get store URL
        console.print("\n[yellow]Enter your Shopify store URL[/yellow]")
        console.print("[dim]Example: yourstore.myshopify.com or just 'yourstore'[/dim]")
        store_url = Prompt.ask("[cyan]Store URL[/cyan]")
        
        # Clean up store URL
        store_url = store_url.strip().lower()
        if not store_url.endswith('.myshopify.com'):
            if '.' not in store_url:
                store_url = f"{store_url}.myshopify.com"
        
        # Ask for authentication method
        console.print("\n[yellow]What type of app credentials do you have?[/yellow]")
        console.print("[dim]1. Admin API access token (Custom app) - Recommended[/dim]")
        console.print("[dim]2. Client ID and Client Secret (OAuth app)[/dim]")
        auth_method = Prompt.ask(
            "[cyan]Choose (1 or 2):[/cyan]",
            choices=["1", "2"],
            default="1"
        )
        
        if auth_method == "1":
            # Direct API token (custom app)
            show_guide = Confirm.ask("\n[yellow]Would you like to see the API setup guide?[/yellow]", default=True)
            if show_guide:
                self.guide_api_setup(oauth_mode=False)
            
            console.print("\n[yellow]Enter your Admin API access token:[/yellow]")
            access_token = Prompt.ask("[cyan]API Token[/cyan]", password=True)
            return name, store_url, access_token, None, None
        
        else:
            # OAuth (client ID and secret)
            show_guide = Confirm.ask("\n[yellow]Would you like to see the OAuth setup guide?[/yellow]", default=True)
            if show_guide:
                self.guide_api_setup(oauth_mode=True)
            
            console.print("\n[yellow]Enter your OAuth credentials:[/yellow]")
            client_id = Prompt.ask("[cyan]Client ID[/cyan]")
            client_secret = Prompt.ask("[cyan]Client Secret[/cyan]", password=True)
            
            # Ask about redirect URI
            console.print("\n[yellow]Redirect URI Configuration:[/yellow]")
            console.print("[dim]The redirect URI must match what's configured in your Shopify app.[/dim]")
            console.print("[dim]Common options:[/dim]")
            console.print("[dim]  - urn:ietf:wg:oauth:2.0:oob (for terminal apps)[/dim]")
            console.print("[dim]  - http://localhost (for local development)[/dim]")
            console.print("[dim]  - Your custom redirect URI[/dim]")
            
            use_default = Confirm.ask("\n[yellow]Use default redirect URI (urn:ietf:wg:oauth:2.0:oob)?[/yellow]", default=True)
            if use_default:
                redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
            else:
                redirect_uri = Prompt.ask("[cyan]Enter your redirect URI[/cyan]", default="urn:ietf:wg:oauth:2.0:oob")
            
            # Show instructions if using default
            if redirect_uri == "urn:ietf:wg:oauth:2.0:oob":
                console.print("\n[yellow]⚠️  Important: Make sure your Shopify app is configured with this redirect URI![/yellow]")
                console.print("[dim]In your Shopify app settings, set Redirect URL to: urn:ietf:wg:oauth:2.0:oob[/dim]")
                console.print("[dim]Location: Apps > Develop apps > Your App > App setup > Redirect URLs[/dim]\n")
            
            # Perform OAuth flow
            access_token = self._oauth_flow(store_url, client_id, client_secret, redirect_uri)
            if not access_token:
                return None, None, None, None, None
            
            return name, store_url, access_token, client_id, client_secret
    
    def _oauth_flow(self, store_url: str, client_id: str, client_secret: str, redirect_uri: str) -> Optional[str]:
        """Handle OAuth authentication flow"""
        oauth = ShopifyOAuth(store_url, client_id, client_secret, redirect_uri=redirect_uri)
        
        # Generate authorization URL
        auth_url = oauth.get_authorization_url()
        
        console.print("\n[bold cyan]Step 1: Authorize the application[/bold cyan]")
        console.print(f"\n[green]Opening authorization URL in your browser...[/green]")
        console.print(f"[dim]URL: {auth_url}[/dim]\n")
        
        # Automatically open the URL in the default browser
        try:
            webbrowser.open(auth_url)
            console.print("[green]✅ Browser opened![/green]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Could not open browser automatically: {e}[/yellow]")
            console.print(f"[cyan]Please manually visit: {auth_url}[/cyan]")
        
        console.print("\n[yellow]After authorizing, you'll see a page with an authorization CODE (not the URL).[/yellow]")
        console.print("[yellow]The code will look something like: abc123def456...[/yellow]")
        console.print("[yellow]⚠️  Make sure you copy the CODE, not the URL![/yellow]\n")
        
        # Get authorization code from user
        console.print("\n[bold cyan]Step 2: Enter authorization code[/bold cyan]")
        console.print("[dim]Paste ONLY the authorization code (not the URL):[/dim]")
        auth_code = Prompt.ask("[cyan]Authorization code[/cyan]")
        
        # Clean up the input - remove URL if user pasted it by mistake
        auth_code = auth_code.strip()
        if auth_code.startswith('http'):
            console.print("[red]❌ It looks like you pasted the URL instead of the code.[/red]")
            console.print("[yellow]Please visit the URL above, approve the permissions, and copy the CODE that appears.[/yellow]")
            retry = Confirm.ask("\n[yellow]Would you like to try entering the code again?[/yellow]", default=True)
            if retry:
                auth_code = Prompt.ask("[cyan]Authorization code[/cyan]")
            else:
                return None
        
        # Exchange code for token
        console.print("\n[cyan]🔄 Exchanging authorization code for access token...[/cyan]")
        access_token = oauth.exchange_code_for_token(auth_code)
        
        if access_token:
            console.print("[green]✅ Successfully obtained access token![/green]")
            return access_token
        else:
            console.print("[red]❌ Failed to obtain access token.[/red]")
            return None
    
    def test_connection(self, store_url: str, access_token: str) -> bool:
        """Test the Shopify API connection"""
        console.print("\n[cyan]🔍 Testing connection to your store...[/cyan]")
        
        client = ShopifyClient(store_url, access_token)
        
        if client.test_connection():
            shop_info = client.get_shop_info()
            if shop_info:
                console.print(f"[green]✅ Successfully connected to {shop_info.get('name', store_url)}![/green]")
                console.print(f"[dim]Store: {shop_info.get('domain', store_url)}[/dim]")
                return True
            else:
                console.print("[green]✅ Connection successful![/green]")
                return True
        else:
            console.print("[red]❌ Connection failed. Please check your credentials.[/red]")
            return False
    
    def run(self) -> bool:
        """Run the complete onboarding process"""
        self.welcome_screen()
        
        # Check if users already exist
        existing_users = self.user_manager.list_users()
        if existing_users:
            add_more = Confirm.ask("\n[yellow]You already have accounts. Add another one?[/yellow]", default=False)
            if not add_more:
                return False
        
        # Collect user info
        result = self.collect_user_info()
        if result[0] is None:  # OAuth failed
            retry = Confirm.ask("\n[yellow]OAuth failed. Would you like to try again?[/yellow]", default=True)
            if retry:
                return self.run()
            return False
        
        name, store_url, access_token, client_id, client_secret = result
        
        # Test connection
        if not self.test_connection(store_url, access_token):
            retry = Confirm.ask("\n[yellow]Connection failed. Would you like to try again?[/yellow]", default=True)
            if retry:
                return self.run()
            return False
        
        # Save user (store client_id and secret if OAuth was used)
        user_id = self.user_manager.add_user(name, store_url, access_token, client_id, client_secret)
        
        if user_id:
            console.print("\n[bold green]🎉 Onboarding complete![/bold green]")
            console.print("[green]You can now use the inventory management system.[/green]\n")
            return True
        else:
            console.print("\n[red]❌ Failed to save account. Please try again.[/red]")
            return False

