"""
User Management Module
Handles multi-user account management with encrypted storage
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from cryptography.fernet import Fernet
from rich.console import Console
from rich.table import Table
import base64
import hashlib

console = Console()


class UserManager:
    """Manages multiple Shopify user accounts"""
    
    def __init__(self, data_dir: str = "./data"):
        """Initialize user manager with data directory"""
        self.data_dir = data_dir
        self.users_file = os.path.join(data_dir, "users.json")
        self.key_file = os.path.join(data_dir, ".key")
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # Initialize encryption key
        self._init_encryption_key()
        
        # Load users
        self.users = self._load_users()
    
    def _init_encryption_key(self):
        """Initialize or load encryption key"""
        if os.path.exists(self.key_file):
            with open(self.key_file, 'rb') as f:
                self.key = f.read()
        else:
            self.key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(self.key)
            # Make key file readable only by owner
            if os.name != 'nt':  # Unix-like systems
                os.chmod(self.key_file, 0o600)
        
        self.cipher = Fernet(self.key)
    
    def _encrypt(self, text: str) -> str:
        """Encrypt sensitive data"""
        return self.cipher.encrypt(text.encode()).decode()
    
    def _decrypt(self, encrypted_text: str) -> str:
        """Decrypt sensitive data"""
        return self.cipher.decrypt(encrypted_text.encode()).decode()
    
    def _load_users(self) -> Dict:
        """Load users from file"""
        if not os.path.exists(self.users_file):
            return {}
        
        try:
            with open(self.users_file, 'r') as f:
                encrypted_data = json.load(f)
            
            # Decrypt user data
            users = {}
            for user_id, user_data in encrypted_data.items():
                user_dict = {
                    "name": user_data["name"],
                    "store_url": self._decrypt(user_data["store_url"]),
                    "access_token": self._decrypt(user_data["access_token"]),
                    "created_at": user_data.get("created_at", "")
                }
                # Add OAuth credentials if they exist
                if "client_id" in user_data:
                    user_dict["client_id"] = self._decrypt(user_data["client_id"])
                if "client_secret" in user_data:
                    user_dict["client_secret"] = self._decrypt(user_data["client_secret"])
                users[user_id] = user_dict
            return users
        except Exception as e:
            console.print(f"[red]Error loading users: {e}[/red]")
            return {}
    
    def _save_users(self):
        """Save users to file with encryption"""
        try:
            # Encrypt user data
            encrypted_data = {}
            for user_id, user_data in self.users.items():
                encrypted_user = {
                    "name": user_data["name"],
                    "store_url": self._encrypt(user_data["store_url"]),
                    "access_token": self._encrypt(user_data["access_token"]),
                    "created_at": user_data.get("created_at", "")
                }
                # Encrypt OAuth credentials if they exist
                if "client_id" in user_data and user_data["client_id"]:
                    encrypted_user["client_id"] = self._encrypt(user_data["client_id"])
                if "client_secret" in user_data and user_data["client_secret"]:
                    encrypted_user["client_secret"] = self._encrypt(user_data["client_secret"])
                encrypted_data[user_id] = encrypted_user
            
            with open(self.users_file, 'w') as f:
                json.dump(encrypted_data, f, indent=2)
            
            # Make file readable only by owner
            if os.name != 'nt':  # Unix-like systems
                os.chmod(self.users_file, 0o600)
            
            return True
        except Exception as e:
            console.print(f"[red]Error saving users: {e}[/red]")
            return False
    
    def _generate_user_id(self, store_url: str) -> str:
        """Generate unique user ID from store URL"""
        return hashlib.md5(store_url.encode()).hexdigest()[:12]
    
    def add_user(self, name: str, store_url: str, access_token: str, 
                 client_id: Optional[str] = None, client_secret: Optional[str] = None) -> Optional[str]:
        """
        Add a new user
        
        Args:
            name: User-friendly name for the account
            store_url: Shopify store URL
            access_token: API access token
            client_id: OAuth client ID (optional)
            client_secret: OAuth client secret (optional)
        
        Returns:
            User ID if successful, None otherwise
        """
        user_id = self._generate_user_id(store_url)
        
        if user_id in self.users:
            console.print("[yellow]⚠️  User with this store already exists![/yellow]")
            return None
        
        user_data = {
            "name": name,
            "store_url": store_url,
            "access_token": access_token,
            "created_at": datetime.now().isoformat()
        }
        
        # Add OAuth credentials if provided
        if client_id:
            user_data["client_id"] = client_id
        if client_secret:
            user_data["client_secret"] = client_secret
        
        self.users[user_id] = user_data
        
        if self._save_users():
            console.print(f"[green]✅ User '{name}' added successfully![/green]")
            return user_id
        else:
            console.print("[red]❌ Failed to save user.[/red]")
            return None
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        return self.users.get(user_id)
    
    def list_users(self) -> List[Dict]:
        """List all users"""
        return [
            {"id": uid, **data}
            for uid, data in self.users.items()
        ]
    
    def delete_user(self, user_id: str) -> bool:
        """Delete a user"""
        if user_id in self.users:
            del self.users[user_id]
            if self._save_users():
                console.print("[green]✅ User deleted successfully![/green]")
                return True
            else:
                console.print("[red]❌ Failed to delete user.[/red]")
                return False
        return False
    
    def display_users(self):
        """Display users in a nice table"""
        if not self.users:
            console.print("[yellow]No users found. Add a user first![/yellow]")
            return
        
        table = Table(title="Registered Users", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=12)
        table.add_column("Name", style="green")
        table.add_column("Store URL", style="blue")
        
        for user_id, user_data in self.users.items():
            # Mask store URL for security
            masked_url = user_data["store_url"][:10] + "..." if len(user_data["store_url"]) > 10 else user_data["store_url"]
            table.add_row(user_id, user_data["name"], masked_url)
        
        console.print(table)

