# Shopify Inventory Management System

A comprehensive terminal-based inventory management system for Shopify stores with multi-user support.

## Features

- 🔐 **Smart Onboarding**: Easy setup wizard for new users
- 👥 **Multi-User Support**: Multiple Shopify accounts can be integrated
- 📦 **Product Management**: List, create, update, and delete products
- 🏷️ **Category Management**: Create and manage product categories
- 📋 **Order Management**: Fetch, update, and track orders
- 📊 **Inventory Tracking**: Real-time inventory management
- 🎨 **Beautiful Terminal UI**: Rich, colorful terminal interface

## Installation

1. Clone or download this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Setup

### Quick Setup (Recommended)

Use the setup helper to create your app and get your token automatically:

```bash
python setup_helper.py
```

This will:
- Open your Shopify Admin in the browser
- Guide you through app creation
- Validate your token
- Save your credentials automatically

### Manual Setup

1. Run the application:
```bash
python main.py
```

2. Follow the onboarding wizard to add your first Shopify account:
   - You'll need your Shopify store URL (e.g., `yourstore.myshopify.com`)
   - API access token (create one in Shopify Admin > Apps > Develop apps)

📖 **New to this? Start with [QUICK_START.md](QUICK_START.md) for a 5-minute setup guide!**

## Getting Your Shopify API Credentials

The system supports two authentication methods:

### Method 1: Custom App (Admin API Token)
1. Go to your Shopify Admin
2. Navigate to **Apps** > **Develop apps**
3. Click **Create an app**
4. Configure Admin API scopes:
   - `read_products`, `write_products`
   - `read_orders`, `write_orders`
   - `read_inventory`, `write_inventory`
5. Install the app and copy the **Admin API access token**

### Method 2: OAuth App (Client ID & Secret)
1. Go to your Shopify Admin
2. Navigate to **Apps** > **Develop apps**
3. Create or select your app
4. **Configure Redirect URL** (IMPORTANT!):
   - Go to **App setup** > **Redirect URLs**
   - Add: `urn:ietf:wg:oauth:2.0:oob` (for terminal apps)
   - Or use your custom redirect URI
   - Click **Save**
5. Copy the **Client ID** and **Client Secret**
6. During setup, the system will guide you through the OAuth flow:
   - The authorization URL will open automatically in your browser
   - Approve the permissions
   - Copy the authorization code you receive
   - Paste it back into the terminal

**Alternative:** You can also create an app using Shopify CLI (`npm init @shopify/app@latest`) and get credentials from your Partners dashboard. See [OAUTH_GUIDE.md](OAUTH_GUIDE.md) for details.

**Note:** The redirect URI you use in the system must exactly match what's configured in your Shopify app settings, otherwise you'll get a "redirect_uri mismatch" error.

📖 **For detailed step-by-step instructions, see [OAUTH_GUIDE.md](OAUTH_GUIDE.md)**

## Distribution

Planning to distribute this application to other users? See [DISTRIBUTION_GUIDE.md](DISTRIBUTION_GUIDE.md) for best practices on packaging and distribution.

**Recommended:** Use **Method 1 (Custom App)** as the default authentication method for the best user experience.

## Usage

The system provides an interactive menu-driven interface. Simply run `python main.py` and follow the prompts.

## Security

- User credentials are encrypted and stored locally
- Each user's data is isolated
- API tokens are never displayed in plain text

## License

MIT License

