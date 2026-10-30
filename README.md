# Aura Commerce OS - Shopify Business Operations & Logistics Dashboard

A powerful, executive-grade business operations dashboard designed to manage your **Shopify Store Orders**, **Multi-Carrier Delivery Tracking & ETAs**, **Payment Gateways & Refunds**, and **Discounts & Customer Rewards**.

---

## 🌟 Key Features

### 1. 🛍️ Shopify Store & Order Command Center
- **Live Sync**: Connect directly to your Shopify Admin REST & GraphQL APIs using your store domain (`your-store.myshopify.com`) and Admin API token (`shpat_...`).
- **Deep Order Inspection**: View customer shipping details, email, contact phone, itemized product lists with SKUs and unit prices, subtotal, taxes, discounts, and order notes.
- **Dynamic Filters**: Filter instantly by `Unfulfilled`, `In Transit`, `Out for Delivery`, `Delivered`, and `Refunded/Cancelled`.
- **Search Engine**: Search by Order ID (`#SH-1049`), customer name, SKU, or tracking waybill number.
- **Export & Print**: One-click generation of printable Packing Slips and CSV exports for bookkeeping and logistics partners.

### 2. 🚚 Multi-Carrier Delivery Partners & Live Tracking
- **Add Custom Delivery Partners**: Easily configure carriers (e.g. DHL Express Worldwide, FedEx, Blue Dart, Delhivery, UPS Worldwide, or your own local delivery fleet).
- **Assign Partner & Dispatch**: Assign an order to any partner with auto-generated or custom waybills and calculated Estimated Delivery Time (ETD).
- **Milestone Timeline Tracker**: Track packages step-by-step:
  1. Picked Up & Dispatched from Warehouse
  2. In-Transit via Air/Road Cargo Hubs
  3. Out for Delivery with Local Driver
  4. Delivered & Signature Acknowledged
- **SLA & Performance Metrics**: Real-time delivery partner SLA rating (e.g. 96.4% on-time dispatch rate, average transit duration).

### 3. 💳 Payment Hub, Transactions Ledger & Instant Refund Center
- **Payment Method Management**: Enable, configure, and monitor payment options (Stripe, PayPal, Razorpay, Cash on Delivery (COD), Apple Pay, and Wire Transfer).
- **Immutable Ledger**: Live audit trail of every captured checkout payment, transaction reference, amount, fee percentage, and net settlement.
- **Instant Refund Processing**:
  - Support for **Full Refund (100%)** or **Custom Partial Refund**.
  - Reason code tagging (Defective item, Customer cancellation, Shipping SLA delay, Inventory mismatch, Goodwill appeasement).
  - Optional automatic item restocking to your Shopify catalog and carrier intercept cancellation.

### 4. 🏷️ Discount & Promotion Engine
- **Create Promotional Coupons**: Percentage-based (`% OFF`) or Fixed Amount (`$ OFF`).
- **Threshold Rules**: Set minimum order purchase requirements, usage limits, and expiration dates.
- **Redemption Analytics**: Track coupon utilization and customer savings.

---

## 🚀 Quick Start (Zero Dependencies)

The server is built with Python 3's native standard library (`sqlite3`, `http.server`, `json`, `urllib`). **No external `pip` install is required.**

### 1. Launch the Server
```bash
python3 server.py
```

### 2. Open the Dashboard in your Browser
Open your browser to:
```
http://localhost:8080
```

---

## ⚙️ Connecting Your Real Shopify Account

1. In your **Shopify Store Admin**:
   - Go to **Settings** &gt; **Apps and sales channels** &gt; **Develop apps**.
   - Create a private app and configure **Admin API scopes**:
     - `read_orders`, `write_orders`
     - `read_fulfillments`, `write_fulfillments`
     - `read_products`, `read_inventory`
   - Click **Install app** and copy the **Admin API Access Token** (begins with `shpat_`).
2. In the **Aura Commerce OS Dashboard**:
   - Navigate to the **Shopify API Keys** tab on the left sidebar.
   - Enter your store domain (e.g., `your-store-name.myshopify.com`) and paste the access token.
   - Click **Save Credentials** and hit **Sync Orders** on the top bar!

---

## 📁 Project Architecture

```
Antigravity/
├── server.py              # Zero-dependency Python 3 REST API & SQLite backend
├── dashboard.db           # SQLite database with orders, partners, payments, and discounts
├── public/
│   └── index.html         # High-performance SPA dashboard (Tailwind CSS, SVG Icons)
└── README.md              # Documentation and operational guide
```

---

## 🛠️ API Reference

- `GET /api/orders` - List all orders with filters (`?status=unfulfilled`, `?search=...`)
- `GET /api/orders/<id>` - Full order details with items, tracking events, and payment ledger
- `POST /api/orders/create` - Place a new simulated or manual order
- `POST /api/orders/assign-partner` - Assign a courier and dispatch shipment
- `POST /api/orders/update-delivery` - Advance shipment checkpoint milestones
- `POST /api/orders/refund` - Process a full or partial refund
- `GET /api/delivery-partners` - List configured couriers
- `POST /api/delivery-partners` - Add a new courier partner
- `GET /api/payment-methods` - List payment options and processing fees
- `POST /api/payment-methods` - Add a payment gateway option
- `GET /api/discounts` - List coupon codes and redemption status
- `POST /api/discounts` - Create a promotional discount code
- `POST /api/shopify/sync` - Synchronize live store orders from Shopify

