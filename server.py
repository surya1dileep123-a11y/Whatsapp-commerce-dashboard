#!/usr/bin/env python3
"""
Aura Commerce OS - WhatsApp Commerce & Courier Logistics Dashboard
Engineered for Direct WhatsApp Selling, Multi-Courier Dispatch & Tracking,
Payment Reconciliation, and Customer Refund Management.
"""

import http.server
import socketserver
import json
import sqlite3
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
import random
import uuid
import re

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dashboard.db")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    # Store & Pickup Address Settings
    c.execute('''
    CREATE TABLE IF NOT EXISTS store_settings (
        id INTEGER PRIMARY KEY,
        business_name TEXT DEFAULT 'Aura Lifestyle & Boutique',
        whatsapp_phone TEXT DEFAULT '+91 98765 43210',
        contact_email TEXT DEFAULT 'orders@auraboutique.com',
        pickup_address TEXT DEFAULT 'Plot 18, Commercial Hub, Sector 44',
        pickup_city TEXT DEFAULT 'Gurugram',
        pickup_state TEXT DEFAULT 'Haryana',
        pickup_pincode TEXT DEFAULT '122003',
        pickup_country TEXT DEFAULT 'India',
        currency TEXT DEFAULT 'INR',
        currency_symbol TEXT DEFAULT '₹',
        shiprocket_token TEXT DEFAULT '',
        delhivery_token TEXT DEFAULT '',
        default_courier TEXT DEFAULT 'dp-shiprocket'
    )
    ''')

    # Delivery Partners / Courier Aggregators
    c.execute('''
    CREATE TABLE IF NOT EXISTS delivery_partners (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        code TEXT NOT NULL,
        service_type TEXT NOT NULL,
        avg_days TEXT NOT NULL,
        tracking_url_pattern TEXT,
        contact_phone TEXT,
        rating REAL DEFAULT 4.8,
        total_shipments INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        color TEXT DEFAULT '#4F46E5',
        supports_auto_pickup INTEGER DEFAULT 1
    )
    ''')

    # Payment Methods
    c.execute('''
    CREATE TABLE IF NOT EXISTS payment_methods (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        provider TEXT NOT NULL,
        fee_percent REAL DEFAULT 0.0,
        is_active INTEGER DEFAULT 1,
        supported_types TEXT DEFAULT 'UPI, GPay, PhonePe, Paytm, COD',
        upi_id TEXT DEFAULT 'aura.business@upi'
    )
    ''')

    # Discounts
    c.execute('''
    CREATE TABLE IF NOT EXISTS discounts (
        id TEXT PRIMARY KEY,
        code TEXT UNIQUE NOT NULL,
        discount_type TEXT NOT NULL,
        value REAL NOT NULL,
        min_order REAL DEFAULT 0,
        usage_limit INTEGER DEFAULT 100,
        times_used INTEGER DEFAULT 0,
        expires_at TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT
    )
    ''')

    # Orders (WhatsApp & Direct)
    c.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        order_source TEXT DEFAULT 'whatsapp', -- whatsapp, manual, web
        order_number TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        customer_phone TEXT NOT NULL,
        customer_email TEXT,
        shipping_address TEXT,
        shipping_city TEXT,
        shipping_state TEXT,
        shipping_zip TEXT,
        shipping_country TEXT DEFAULT 'India',
        raw_whatsapp_text TEXT,
        items_json TEXT NOT NULL,
        subtotal REAL NOT NULL,
        tax REAL NOT NULL,
        discount_amount REAL DEFAULT 0,
        total REAL NOT NULL,
        currency TEXT DEFAULT 'INR',
        payment_gateway TEXT DEFAULT 'UPI / Direct Bank',
        payment_status TEXT NOT NULL, -- paid, pending, cod, refunded, partially_refunded
        fulfillment_status TEXT NOT NULL, -- unfulfilled, pickup_scheduled, in_transit, out_for_delivery, delivered, cancelled
        delivery_partner_id TEXT,
        delivery_partner_name TEXT,
        tracking_number TEXT,
        pickup_time_slot TEXT,
        package_weight_kg REAL DEFAULT 0.8,
        estimated_delivery TEXT,
        notes TEXT,
        tags TEXT,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY(delivery_partner_id) REFERENCES delivery_partners(id)
    )
    ''')

    # Tracking Events
    c.execute('''
    CREATE TABLE IF NOT EXISTS tracking_events (
        id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        status TEXT NOT NULL,
        location TEXT NOT NULL,
        description TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id)
    )
    ''')

    # Payment Transactions & Refunds
    c.execute('''
    CREATE TABLE IF NOT EXISTS payment_transactions (
        id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        transaction_type TEXT NOT NULL, -- payment, refund, cod_remittance
        gateway TEXT NOT NULL,
        reference_id TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'INR',
        status TEXT NOT NULL,
        reason TEXT,
        created_at TEXT,
        FOREIGN KEY(order_id) REFERENCES orders(id)
    )
    ''')

    conn.commit()

    # Check if empty, seed rich WhatsApp orders & couriers
    c.execute("SELECT COUNT(*) FROM delivery_partners")
    if c.fetchone()[0] == 0:
        seed_whatsapp_commerce_data(conn)

    conn.close()

def seed_whatsapp_commerce_data(conn):
    c = conn.cursor()
    now = datetime.now()

    # Store Settings
    c.execute('''
    INSERT OR REPLACE INTO store_settings (
        id, business_name, whatsapp_phone, contact_email,
        pickup_address, pickup_city, pickup_state, pickup_pincode, pickup_country,
        currency, currency_symbol, default_courier
    ) VALUES (
        1, 'Aura Lifestyle & Boutique', '+91 98765 43210', 'orders@auraboutique.com',
        'Plot 18, Commercial Hub, Sector 44', 'Gurugram', 'Haryana', '122003', 'India',
        'INR', '₹', 'dp-shiprocket'
    )
    ''')

    # Delivery Partners for Direct WhatsApp Business
    partners = [
        ("dp-shiprocket", "Shiprocket (Multi-Courier Aggregator)", "SHIPROCKET", "Automated Doorstep Pickup", "1-3 Business Days", "https://shiprocket.co/tracking/{TRACKING}", "+91 (92666) 23000", 4.9, 1420, 1, "#2563EB", 1),
        ("dp-delhivery", "Delhivery Direct Logistics", "DELHIVERY", "Surface & Express Air", "2-4 Business Days", "https://www.delhivery.com/track/package/{TRACKING}", "+91 (8069) 859-999", 4.8, 2180, 1, "#059669", 1),
        ("dp-bluedart", "Blue Dart Apex Air Express", "BLUEDART", "Air Express Priority", "1-2 Business Days", "https://www.bluedart.com/tracking?track={TRACKING}", "+91 (1860) 233-1234", 4.9, 980, 1, "#DC2626", 1),
        ("dp-porter", "Porter / Borzo Local Same-Day", "PORTER", "Hyperlocal 2-Hour Delivery", "Same Day (2-4 Hours)", "https://porter.in/track/{TRACKING}", "+91 (4410) 992-000", 4.95, 620, 1, "#0D9488", 1),
        ("dp-dtdc", "DTDC Express Courier", "DTDC", "Domestic Air & Ground", "3-5 Business Days", "https://www.dtdc.in/tracking/{TRACKING}", "+91 (7305) 730-500", 4.7, 1120, 1, "#D97706", 1),
        ("dp-custom", "Store Delivery Boy / Custom Fleet", "STOREFLEET", "Local Direct Handover", "Same Day / Next Day", "https://track.auraboutique.com/{TRACKING}", "+91 98765 43210", 4.9, 310, 1, "#9333EA", 0)
    ]
    c.executemany('''
    INSERT INTO delivery_partners (id, name, code, service_type, avg_days, tracking_url_pattern, contact_phone, rating, total_shipments, is_active, color, supports_auto_pickup)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', partners)

    # Payment Methods
    methods = [
        ("pm-upi", "UPI Direct (GPay, PhonePe, Paytm, QR)", "UPI", 0.0, 1, "Direct Bank Transfer, UPI QR, VPA", "aura.business@okhdfcbank"),
        ("pm-cod", "Cash on Delivery (COD Verified)", "CashOnDelivery", 1.5, 1, "Courier Cash Collection at Doorstep", ""),
        ("pm-razorpay", "Razorpay WhatsApp Payment Link", "Razorpay", 2.0, 1, "Cards, NetBanking, EMI, Wallets", "https://rzp.io/l/aura"),
        ("pm-stripe", "Stripe International Cards", "Stripe", 2.9, 1, "International Visa, Mastercard, Amex", ""),
        ("pm-bank", "NEFT / IMPS Bank Transfer", "DirectBank", 0.0, 1, "Bank Wire Transfer to Current Account", "HDFC0001234 / 502000849102")
    ]
    c.executemany('''
    INSERT INTO payment_methods (id, name, provider, fee_percent, is_active, supported_types, upi_id)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', methods)

    # Discounts
    discounts = [
        ("disc-1", "WAOFF10", "percentage", 10.0, 500.0, 1000, 342, (now + timedelta(days=90)).strftime("%Y-%m-%d"), 1, now.strftime("%Y-%m-%d")),
        ("disc-2", "FREESHIP", "fixed", 100.0, 1200.0, 2000, 890, (now + timedelta(days=120)).strftime("%Y-%m-%d"), 1, now.strftime("%Y-%m-%d")),
        ("disc-3", "FIRSTBUY200", "fixed", 200.0, 1500.0, 500, 115, (now + timedelta(days=60)).strftime("%Y-%m-%d"), 1, now.strftime("%Y-%m-%d"))
    ]
    c.executemany('''
    INSERT INTO discounts (id, code, discount_type, value, min_order, usage_limit, times_used, expires_at, is_active, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', discounts)

    # Sample Items
    sample_items = [
        {"id": "p1", "title": "Aura Studio Headphones Pro", "sku": "AUR-HP-001", "price": 4999.00, "qty": 1, "image": "🎧"},
        {"id": "p2", "title": "Minimalist Titanium Watch", "sku": "AUR-WT-004", "price": 2899.00, "qty": 1, "image": "⌚"},
        {"id": "p3", "title": "Handcrafted Silk Kurta Set", "sku": "AUR-KT-012", "price": 3499.00, "qty": 1, "image": "👘"},
        {"id": "p4", "title": "Wireless Ergonomic Keyboard", "sku": "AUR-KB-009", "price": 2199.00, "qty": 1, "image": "⌨️"},
        {"id": "p5", "title": "Artisanal Ceramic Pour-Over Set", "sku": "AUR-CF-003", "price": 1250.00, "qty": 2, "image": "☕"},
        {"id": "p6", "title": "Organic Mulberry Silk Pillowcases", "sku": "AUR-LK-020", "price": 1499.00, "qty": 1, "image": "🛏️"}
    ]

    # Sample Realistic WhatsApp Orders
    orders_data = [
        {
            "id": "ord-wa-101",
            "order_number": "#WA-2041",
            "customer_name": "Pooja Hegde",
            "customer_phone": "+91 98200 44551",
            "customer_email": "pooja.hegde@gmail.com",
            "shipping_address": "Flat 702, Skyline Residency, Linking Road, Bandra West",
            "shipping_city": "Mumbai",
            "shipping_state": "Maharashtra",
            "shipping_zip": "400050",
            "shipping_country": "India",
            "raw_whatsapp_text": "Hi! I want to order the Handcrafted Silk Kurta Set in Size M. Please ship to: Pooja Hegde, Flat 702, Skyline Residency, Linking Road, Bandra West, Mumbai 400050. Phone 9820044551. Paid ₹3499 via Google Pay just now!",
            "items": [sample_items[2]],
            "subtotal": 3499.00,
            "tax": 174.95,
            "discount_amount": 200.00,
            "total": 3473.95,
            "payment_gateway": "UPI (Google Pay)",
            "payment_status": "paid",
            "fulfillment_status": "in_transit",
            "delivery_partner_id": "dp-shiprocket",
            "delivery_partner_name": "Shiprocket (Blue Dart Air)",
            "tracking_number": "SR-BLU-9948271049",
            "pickup_time_slot": "Picked up today at 11:30 AM",
            "package_weight_kg": 0.6,
            "estimated_delivery": (now + timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
            "notes": "Verified GPay screenshot (UTR: 329104928120)",
            "tags": "WhatsApp Order, GPay Verified, Priority Air",
            "days_ago": 1,
            "events": [
                ("in_transit", "Mumbai Domestic Air Cargo Hub", "Package reached destination hub; assigned to Bandra delivery agent"),
                ("pickup_scheduled", "Gurugram Warehouse Center", "Courier picked up parcel from merchant premises. AWB generated.")
            ]
        },
        {
            "id": "ord-wa-102",
            "order_number": "#WA-2042",
            "customer_name": "Karthik Raja",
            "customer_phone": "+91 97410 88219",
            "customer_email": "karthik.r@techmail.com",
            "shipping_address": "42, 12th Main, 4th Block, Koramangala",
            "shipping_city": "Bengaluru",
            "shipping_state": "Karnataka",
            "shipping_zip": "560034",
            "shipping_country": "India",
            "raw_whatsapp_text": "Hello, need 1x Aura Studio Headphones Pro. Address: Karthik Raja, 42, 12th Main, 4th Block, Koramangala, Bangalore 560034. Ph: 9741088219. Please dispatch via Fast courier.",
            "items": [sample_items[0]],
            "subtotal": 4999.00,
            "tax": 249.95,
            "discount_amount": 0.0,
            "total": 5248.95,
            "payment_gateway": "UPI (PhonePe)",
            "payment_status": "paid",
            "fulfillment_status": "out_for_delivery",
            "delivery_partner_id": "dp-delhivery",
            "delivery_partner_name": "Delhivery Direct Logistics",
            "tracking_number": "DEL-BLR-44019283",
            "pickup_time_slot": "Picked up yesterday",
            "package_weight_kg": 0.9,
            "estimated_delivery": (now + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M"),
            "notes": "PhonePe payment verified.",
            "tags": "WhatsApp Direct, Express Courier",
            "days_ago": 2,
            "events": [
                ("out_for_delivery", "Koramangala Delivery Depot, Bengaluru", "Rider Ramesh is out for delivery. ETA within 3 hours"),
                ("in_transit", "Bengaluru Central Sort Center", "Bag opened and parcel sorted to Koramangala route"),
                ("pickup_scheduled", "Merchant Warehouse, Gurugram", "Delhivery rider collected parcel")
            ]
        },
        {
            "id": "ord-wa-103",
            "order_number": "#WA-2043",
            "customer_name": "Ananya Sen",
            "customer_email": "ananya.sen@outlook.com",
            "customer_phone": "+91 98300 12948",
            "shipping_address": "84 Park Street, Flat 3B",
            "shipping_city": "Kolkata",
            "shipping_state": "West Bengal",
            "shipping_zip": "700016",
            "shipping_country": "India",
            "raw_whatsapp_text": "Hi, want to buy the Ceramic Pour-Over Set (2 qty). Shipping to: Ananya Sen, 84 Park Street, Flat 3B, Kolkata 700016. Ph: 9830012948. Cash on delivery please.",
            "items": [sample_items[4]],
            "subtotal": 2500.00,
            "tax": 125.00,
            "discount_amount": 100.00,
            "total": 2525.00,
            "payment_gateway": "Cash on Delivery (COD)",
            "payment_status": "cod",
            "fulfillment_status": "unfulfilled",
            "delivery_partner_id": None,
            "delivery_partner_name": None,
            "tracking_number": None,
            "pickup_time_slot": None,
            "package_weight_kg": 1.2,
            "estimated_delivery": None,
            "notes": "COD order confirmed on WhatsApp call.",
            "tags": "COD Order, Ready for Courier Booking",
            "days_ago": 0,
            "events": []
        },
        {
            "id": "ord-wa-104",
            "order_number": "#WA-2044",
            "customer_name": "Vikramaditya Rao",
            "customer_email": "vikram.rao@hyderabad.co",
            "customer_phone": "+91 99890 33441",
            "shipping_address": "Villa 12, Jubilee Hills Road No. 36",
            "shipping_city": "Hyderabad",
            "shipping_state": "Telangana",
            "shipping_zip": "500033",
            "shipping_country": "India",
            "raw_whatsapp_text": "Hey! Need 1 Minimalist Titanium Watch urgently. Address: Vikramaditya Rao, Villa 12, Jubilee Hills Rd 36, Hyderabad 500033. Ph: 9989033441. Paytm transferred.",
            "items": [sample_items[1]],
            "subtotal": 2899.00,
            "tax": 144.95,
            "discount_amount": 0.0,
            "total": 3043.95,
            "payment_gateway": "UPI (Paytm)",
            "payment_status": "paid",
            "fulfillment_status": "unfulfilled",
            "delivery_partner_id": None,
            "delivery_partner_name": None,
            "tracking_number": None,
            "pickup_time_slot": None,
            "package_weight_kg": 0.4,
            "estimated_delivery": None,
            "notes": "Customer requested fastest express option.",
            "tags": "WhatsApp Prepaid, Urgent Dispatch",
            "days_ago": 0,
            "events": []
        },
        {
            "id": "ord-wa-105",
            "order_number": "#WA-2045",
            "customer_name": "Rohan Deshmukh",
            "customer_email": "rohan.d@pune.ac.in",
            "customer_phone": "+91 98500 77112",
            "shipping_address": "B-14, Koregaon Park, North Main Road",
            "shipping_city": "Pune",
            "shipping_state": "Maharashtra",
            "shipping_zip": "411001",
            "shipping_country": "India",
            "raw_whatsapp_text": "Order for Organic Mulberry Silk Pillowcases. Delivered to Pune. Refund issued due to wrong size ordered.",
            "items": [sample_items[5]],
            "subtotal": 1499.00,
            "tax": 74.95,
            "discount_amount": 0.0,
            "total": 1573.95,
            "payment_gateway": "UPI (Google Pay)",
            "payment_status": "refunded",
            "fulfillment_status": "cancelled",
            "delivery_partner_id": "dp-delhivery",
            "delivery_partner_name": "Delhivery Direct Logistics",
            "tracking_number": "DEL-PUN-992011",
            "pickup_time_slot": None,
            "package_weight_kg": 0.3,
            "estimated_delivery": None,
            "notes": "Full refund of ₹1573.95 sent back via UPI.",
            "tags": "Refund Completed, WhatsApp Confirmation Sent",
            "days_ago": 3,
            "events": [
                ("cancelled", "Merchant Hub", "Shipment cancelled before courier pickup; customer refunded via UPI")
            ]
        }
    ]

    for ord_info in orders_data:
        order_created = (now - timedelta(days=ord_info["days_ago"], hours=random.randint(1, 8))).strftime("%Y-%m-%d %H:%M:%S")
        c.execute('''
        INSERT INTO orders (
            id, order_source, order_number, customer_name, customer_phone, customer_email,
            shipping_address, shipping_city, shipping_state, shipping_zip, shipping_country,
            raw_whatsapp_text, items_json, subtotal, tax, discount_amount, total, currency,
            payment_gateway, payment_status, fulfillment_status,
            delivery_partner_id, delivery_partner_name, tracking_number, pickup_time_slot,
            package_weight_kg, estimated_delivery, notes, tags, created_at, updated_at
        ) VALUES (?, 'whatsapp', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'INR', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ord_info["id"], ord_info["order_number"], ord_info["customer_name"], ord_info["customer_phone"], ord_info["customer_email"],
            ord_info["shipping_address"], ord_info["shipping_city"], ord_info["shipping_state"], ord_info["shipping_zip"], ord_info["shipping_country"],
            ord_info["raw_whatsapp_text"], json.dumps(ord_info["items"]), ord_info["subtotal"], ord_info["tax"], ord_info["discount_amount"],
            ord_info["total"], ord_info["payment_gateway"], ord_info["payment_status"], ord_info["fulfillment_status"],
            ord_info["delivery_partner_id"], ord_info["delivery_partner_name"], ord_info["tracking_number"], ord_info["pickup_time_slot"],
            ord_info["package_weight_kg"], ord_info["estimated_delivery"], ord_info["notes"], ord_info["tags"], order_created, order_created
        ))

        # Initial payment record
        tx_id = f"tx-{uuid.uuid4().hex[:10]}"
        c.execute('''
        INSERT INTO payment_transactions (id, order_id, transaction_type, gateway, reference_id, amount, currency, status, reason, created_at)
        VALUES (?, ?, 'payment', ?, ?, ?, 'INR', ?, 'WhatsApp Order Booking', ?)
        ''', (
            tx_id, ord_info["id"], ord_info["payment_gateway"], f"UPI-{random.randint(1000000000, 9999999999)}",
            ord_info["total"],
            "success" if ord_info["payment_status"] in ("paid", "refunded") else ("pending" if ord_info["payment_status"] == "cod" else "pending"),
            order_created
        ))

        if ord_info["payment_status"] == "refunded":
            ref_id = f"ref-{uuid.uuid4().hex[:10]}"
            c.execute('''
            INSERT INTO payment_transactions (id, order_id, transaction_type, gateway, reference_id, amount, currency, status, reason, created_at)
            VALUES (?, ?, 'refund', ?, ?, ?, 'INR', 'success', 'WhatsApp Customer Cancellation', ?)
            ''', (
                ref_id, ord_info["id"], ord_info["payment_gateway"], f"REF-UPI-{random.randint(1000000000, 9999999999)}",
                ord_info["total"], (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
            ))

        for idx, (st, loc, desc) in enumerate(ord_info["events"]):
            ev_id = f"trk-{uuid.uuid4().hex[:10]}"
            ev_time = (now - timedelta(hours=(idx + 1) * 6)).strftime("%Y-%m-%d %H:%M:%S")
            c.execute('''
            INSERT INTO tracking_events (id, order_id, status, location, description, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (ev_id, ord_info["id"], st, loc, desc, ev_time))

    conn.commit()
    print("WhatsApp Commerce & Multi-Courier database initialized successfully.")

class DashboardRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode('utf-8'))

    def read_json_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        return json.loads(body.decode('utf-8'))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/health":
            self.send_json({"status": "healthy", "service": "Aura Commerce OS", "mode": "WhatsApp & Courier Logistics", "time": datetime.now().isoformat()})
            return

        if path == "/api/settings":
            conn = get_db()
            row = conn.execute("SELECT * FROM store_settings WHERE id = 1").fetchone()
            conn.close()
            self.send_json(dict(row) if row else {})
            return

        if path == "/api/analytics":
            conn = get_db()
            c = conn.cursor()

            c.execute("SELECT SUM(total) FROM orders WHERE payment_status IN ('paid', 'cod')")
            total_rev = c.fetchone()[0] or 0.0

            c.execute("SELECT COUNT(*) FROM orders")
            total_orders = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM orders WHERE fulfillment_status = 'unfulfilled'")
            unfulfilled = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM orders WHERE fulfillment_status IN ('in_transit', 'out_for_delivery', 'pickup_scheduled')")
            in_transit = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM orders WHERE fulfillment_status = 'delivered'")
            delivered = c.fetchone()[0]

            c.execute("SELECT SUM(amount) FROM payment_transactions WHERE transaction_type = 'refund' AND status = 'success'")
            total_refunds = c.fetchone()[0] or 0.0

            partners = [dict(r) for r in conn.execute("SELECT name, total_shipments, rating, avg_days FROM delivery_partners").fetchall()]

            gateways = [dict(r) for r in conn.execute('''
                SELECT payment_gateway, COUNT(*) as count, SUM(total) as volume
                FROM orders GROUP BY payment_gateway
            ''').fetchall()]

            conn.close()
            self.send_json({
                "total_revenue": round(total_rev, 2),
                "total_orders": total_orders,
                "unfulfilled_orders": unfulfilled,
                "in_transit_orders": in_transit,
                "delivered_orders": delivered,
                "total_refunds": round(total_refunds, 2),
                "partners": partners,
                "gateways": gateways
            })
            return

        if path == "/api/orders":
            conn = get_db()
            c = conn.cursor()

            status_filter = query.get("status", [None])[0]
            search_query = query.get("search", [None])[0]

            sql = "SELECT * FROM orders WHERE 1=1"
            params = []

            if status_filter and status_filter != "all":
                if status_filter in ("unfulfilled", "in_transit", "delivered", "out_for_delivery", "cancelled"):
                    sql += " AND fulfillment_status = ?"
                    params.append(status_filter)
                elif status_filter in ("paid", "pending", "cod", "refunded"):
                    sql += " AND payment_status = ?"
                    params.append(status_filter)

            if search_query:
                sql += " AND (order_number LIKE ? OR customer_name LIKE ? OR customer_phone LIKE ? OR tracking_number LIKE ?)"
                wild = f"%{search_query}%"
                params.extend([wild, wild, wild, wild])

            sql += " ORDER BY created_at DESC"
            rows = c.execute(sql, params).fetchall()
            orders = []
            for r in rows:
                o = dict(r)
                o["items"] = json.loads(o["items_json"]) if o.get("items_json") else []
                orders.append(o)

            conn.close()
            self.send_json(orders)
            return

        if path.startswith("/api/orders/"):
            parts = path.strip("/").split("/")
            if len(parts) == 3:
                order_id = parts[2]
                conn = get_db()
                o_row = conn.execute("SELECT * FROM orders WHERE id = ? OR order_number = ?", (order_id, order_id)).fetchone()
                if not o_row:
                    conn.close()
                    self.send_json({"error": "Order not found"}, 404)
                    return

                order = dict(o_row)
                order["items"] = json.loads(order["items_json"]) if order.get("items_json") else []

                evs = conn.execute("SELECT * FROM tracking_events WHERE order_id = ? ORDER BY timestamp DESC", (order["id"],)).fetchall()
                order["tracking_events"] = [dict(e) for e in evs]

                txs = conn.execute("SELECT * FROM payment_transactions WHERE order_id = ? ORDER BY created_at DESC", (order["id"],)).fetchall()
                order["transactions"] = [dict(t) for t in txs]

                conn.close()
                self.send_json(order)
                return

        if path == "/api/delivery-partners":
            conn = get_db()
            rows = conn.execute("SELECT * FROM delivery_partners ORDER BY total_shipments DESC").fetchall()
            conn.close()
            self.send_json([dict(r) for r in rows])
            return

        if path == "/api/payment-methods":
            conn = get_db()
            rows = conn.execute("SELECT * FROM payment_methods ORDER BY fee_percent ASC").fetchall()
            conn.close()
            self.send_json([dict(r) for r in rows])
            return

        if path == "/api/transactions":
            conn = get_db()
            rows = conn.execute('''
                SELECT pt.*, o.order_number, o.customer_name
                FROM payment_transactions pt
                LEFT JOIN orders o ON pt.order_id = o.id
                ORDER BY pt.created_at DESC
            ''').fetchall()
            conn.close()
            self.send_json([dict(r) for r in rows])
            return

        if path == "/api/discounts":
            conn = get_db()
            rows = conn.execute("SELECT * FROM discounts ORDER BY created_at DESC").fetchall()
            conn.close()
            self.send_json([dict(r) for r in rows])
            return

        # Client presentation route
        if path in ("/client-view", "/share", "/preview"):
            self.path = "/index.html"
            return super().do_GET()

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/settings":
            body = self.read_json_body()
            conn = get_db()
            conn.execute('''
            UPDATE store_settings
            SET business_name = ?, whatsapp_phone = ?, contact_email = ?,
                pickup_address = ?, pickup_city = ?, pickup_state = ?, pickup_pincode = ?, pickup_country = ?,
                currency = ?, currency_symbol = ?, default_courier = ?, shiprocket_token = ?, delhivery_token = ?
            WHERE id = 1
            ''', (
                body.get("business_name", "Aura Lifestyle & Boutique"),
                body.get("whatsapp_phone", "+91 98765 43210"),
                body.get("contact_email", "orders@auraboutique.com"),
                body.get("pickup_address", "Plot 18, Commercial Hub, Sector 44"),
                body.get("pickup_city", "Gurugram"),
                body.get("pickup_state", "Haryana"),
                body.get("pickup_pincode", "122003"),
                body.get("pickup_country", "India"),
                body.get("currency", "INR"),
                body.get("currency_symbol", "₹"),
                body.get("default_courier", "dp-shiprocket"),
                body.get("shiprocket_token", ""),
                body.get("delhivery_token", "")
            ))
            conn.commit()
            conn.close()
            self.send_json({"success": True, "message": "Store and Pickup Address settings updated successfully!"})
            return

        # 1. SMART WHATSAPP ORDER INTAKE / PARSER
        if path == "/api/orders/from-whatsapp":
            body = self.read_json_body()
            raw_text = body.get("raw_text", "").strip()
            customer_name = body.get("customer_name")
            phone = body.get("phone", "")
            address = body.get("address", "")
            city = body.get("city", "")
            state = body.get("state", "")
            zip_code = body.get("pincode", "")
            items_input = body.get("items", [])
            payment_mode = body.get("payment_mode", "UPI (Google Pay)")
            payment_status = body.get("payment_status", "paid")

            # Simple automatic extraction from raw WhatsApp text if not provided
            if raw_text and not customer_name:
                phone_match = re.search(r'(\+?\d{10,13})', raw_text)
                if phone_match: phone = phone_match.group(1)
                pincode_match = re.search(r'\b(\d{6})\b', raw_text)
                if pincode_match: zip_code = pincode_match.group(1)
                customer_name = "WhatsApp Customer"
                # If name mentioned
                name_match = re.search(r'(?:name|i am|this is)\s*[:\-]?\s*([A-Za-z ]{2,30})', raw_text, re.IGNORECASE)
                if name_match: customer_name = name_match.group(1).strip()
                address = raw_text[:200]

            if not customer_name: customer_name = "WhatsApp Customer"

            if not items_input:
                items_input = [{"title": "Custom WhatsApp Order Item", "sku": "WA-CUST-01", "price": 1499.00, "qty": 1, "image": "🛍️"}]

            subtotal = sum(i.get("price", 0) * i.get("qty", 1) for i in items_input)
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax, 2)

            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM orders")
            cnt = c.fetchone()[0]
            ord_num = f"#WA-{2046 + cnt}"
            ord_id = f"ord-wa-{uuid.uuid4().hex[:8]}"
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            conn.execute('''
            INSERT INTO orders (
                id, order_source, order_number, customer_name, customer_phone, customer_email,
                shipping_address, shipping_city, shipping_state, shipping_zip, shipping_country,
                raw_whatsapp_text, items_json, subtotal, tax, discount_amount, total, currency,
                payment_gateway, payment_status, fulfillment_status,
                delivery_partner_id, delivery_partner_name, tracking_number, pickup_time_slot,
                package_weight_kg, estimated_delivery, notes, tags, created_at, updated_at
            ) VALUES (?, 'whatsapp', ?, ?, ?, ?, ?, ?, ?, ?, 'India', ?, ?, ?, ?, 0.0, ?, 'INR', ?, ?, 'unfulfilled', NULL, NULL, NULL, NULL, 0.8, NULL, ?, 'WhatsApp Direct Order', ?, ?)
            ''', (
                ord_id, ord_num, customer_name, phone or "+91 90000 00000", body.get("email", ""),
                address or "Address provided via WhatsApp chat", city or "Local", state or "State", zip_code or "000000",
                raw_text, json.dumps(items_input), subtotal, tax, total,
                payment_mode, payment_status,
                body.get("notes", "WhatsApp order received and logged into system"), now_str, now_str
            ))

            tx_id = f"tx-{uuid.uuid4().hex[:10]}"
            conn.execute('''
            INSERT INTO payment_transactions (id, order_id, transaction_type, gateway, reference_id, amount, currency, status, reason, created_at)
            VALUES (?, ?, 'payment', ?, ?, ?, 'INR', ?, 'WhatsApp Order Booking', ?)
            ''', (
                tx_id, ord_id, payment_mode, f"TXN-{random.randint(1000000000, 9999999999)}",
                total, "success" if payment_status == "paid" else "pending", now_str
            ))

            conn.commit()
            conn.close()

            self.send_json({
                "success": True,
                "id": ord_id,
                "order_number": ord_num,
                "total": total,
                "message": f"WhatsApp Order {ord_num} created successfully! Ready for courier booking."
            })
            return

        # 2. AUTOMATED COURIER PICKUP & WAYBILL DISPATCH (Shiprocket / Delhivery / Porter)
        if path == "/api/logistics/book-pickup":
            body = self.read_json_body()
            order_id = body.get("order_id")
            partner_id = body.get("partner_id")
            pickup_slot = body.get("pickup_slot", "Today between 2:00 PM - 5:00 PM")
            weight = float(body.get("package_weight_kg", 0.8))

            if not order_id or not partner_id:
                self.send_json({"error": "order_id and partner_id are required"}, 400)
                return

            conn = get_db()
            partner = conn.execute("SELECT * FROM delivery_partners WHERE id = ?", (partner_id,)).fetchone()
            order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            store = conn.execute("SELECT * FROM store_settings WHERE id = 1").fetchone()

            if not partner or not order:
                conn.close()
                self.send_json({"error": "Invalid order or courier partner"}, 400)
                return

            # Generate real-style carrier AWB Waybill
            awb = f"{partner['code']}-{random.randint(1000000000, 9999999999)}"
            est_days = 2
            if "Same Day" in partner["avg_days"]: est_days = 0
            elif "1-2" in partner["avg_days"] or "1-3" in partner["avg_days"]: est_days = 2
            else: est_days = 3

            est_delivery = (datetime.now() + timedelta(days=est_days)).strftime("%Y-%m-%d %H:%M")
            if est_days == 0:
                est_delivery = "Today within 3-4 Hours"

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            conn.execute('''
            UPDATE orders
            SET delivery_partner_id = ?, delivery_partner_name = ?, tracking_number = ?,
                pickup_time_slot = ?, package_weight_kg = ?, estimated_delivery = ?,
                fulfillment_status = 'pickup_scheduled', updated_at = ?
            WHERE id = ?
            ''', (partner_id, partner["name"], awb, pickup_slot, weight, est_delivery, now_str, order_id))

            conn.execute("UPDATE delivery_partners SET total_shipments = total_shipments + 1 WHERE id = ?", (partner_id,))

            # Add Tracking Event
            ev_id = f"trk-{uuid.uuid4().hex[:10]}"
            pickup_loc = f"{store['pickup_city']}, {store['pickup_state']}" if store else "Merchant Warehouse"
            conn.execute('''
            INSERT INTO tracking_events (id, order_id, status, location, description, timestamp)
            VALUES (?, ?, 'pickup_scheduled', ?, ?, ?)
            ''', (
                ev_id, order_id, pickup_loc,
                f"Courier pickup booked via {partner['name']}. Assigned Rider Slot: {pickup_slot}. Waybill/AWB: {awb}",
                now_str
            ))

            conn.commit()
            conn.close()

            # Pre-generate WhatsApp message for the customer
            cust_msg = (
                f"Hi {order['customer_name']}! 👋 Great news: Your order {order['order_number']} is packed and scheduled for courier pickup "
                f"via {partner['name']}.\n"
                f"📦 Tracking AWB: {awb}\n"
                f"🚚 Expected Delivery: {est_delivery}\n"
                f"Thank you for ordering with us!"
            )

            self.send_json({
                "success": True,
                "awb": awb,
                "courier": partner["name"],
                "pickup_slot": pickup_slot,
                "estimated_delivery": est_delivery,
                "whatsapp_customer_message": cust_msg,
                "whatsapp_link": f"https://wa.me/{order['customer_phone'].replace(' ', '').replace('+', '')}?text={urllib.parse.quote(cust_msg)}",
                "message": f"Courier pickup successfully booked with {partner['name']}! Rider scheduled for {pickup_slot}."
            })
            return

        # 3. ADVANCE COURIER MILESTONE
        if path == "/api/logistics/update-status":
            body = self.read_json_body()
            order_id = body.get("order_id")
            new_status = body.get("status") # in_transit, out_for_delivery, delivered
            location = body.get("location", "En-route Cargo Hub")
            desc = body.get("description", "Status updated by courier network")

            conn = get_db()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            conn.execute("UPDATE orders SET fulfillment_status = ?, updated_at = ? WHERE id = ?", (new_status, now_str, order_id))
            ev_id = f"trk-{uuid.uuid4().hex[:10]}"
            conn.execute('''
            INSERT INTO tracking_events (id, order_id, status, location, description, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (ev_id, order_id, new_status, location, desc, now_str))

            conn.commit()
            conn.close()
            self.send_json({"success": True, "message": f"Delivery updated to {new_status}"})
            return

        # 4. REFUND PROCESSING
        if path == "/api/orders/refund":
            body = self.read_json_body()
            order_id = body.get("order_id")
            refund_type = body.get("type", "full")
            refund_amount = float(body.get("amount", 0.0))
            reason = body.get("reason", "Customer requested cancellation via WhatsApp")
            cancel_pickup = body.get("cancel_pickup", True)

            conn = get_db()
            order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not order:
                conn.close()
                self.send_json({"error": "Order not found"}, 404)
                return

            if refund_type == "full" or refund_amount >= order["total"]:
                refund_amount = order["total"]
                new_status = "refunded"
            else:
                new_status = "partially_refunded"

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ref_tx_id = f"ref-{uuid.uuid4().hex[:10]}"
            conn.execute('''
            INSERT INTO payment_transactions (id, order_id, transaction_type, gateway, reference_id, amount, currency, status, reason, created_at)
            VALUES (?, ?, 'refund', ?, ?, ?, ?, 'success', ?, ?)
            ''', (
                ref_tx_id, order_id, order["payment_gateway"], f"REF-UPI-{random.randint(1000000000, 9999999999)}",
                refund_amount, order["currency"], reason, now_str
            ))

            conn.execute("UPDATE orders SET payment_status = ?, updated_at = ? WHERE id = ?", (new_status, now_str, order_id))

            if cancel_pickup and new_status == "refunded":
                conn.execute("UPDATE orders SET fulfillment_status = 'cancelled' WHERE id = ?", (order_id,))
                ev_id = f"trk-{uuid.uuid4().hex[:10]}"
                conn.execute('''
                INSERT INTO tracking_events (id, order_id, status, location, description, timestamp)
                VALUES (?, ?, 'cancelled', 'Merchant Operations Hub', ?, ?)
                ''', (ev_id, order_id, f"Courier pickup cancelled. Refund of {order['currency']} {refund_amount:.2f} processed: {reason}", now_str))

            conn.commit()
            conn.close()

            wa_refund_msg = (
                f"Hi {order['customer_name']}, we have processed a refund of ₹{refund_amount:.2f} for your order {order['order_number']}.\n"
                f"Reference ID: {ref_tx_id}\n"
                f"Reason: {reason}\n"
                f"Thank you for contacting us on WhatsApp."
            )

            self.send_json({
                "success": True,
                "refund_id": ref_tx_id,
                "amount": refund_amount,
                "status": new_status,
                "whatsapp_message": wa_refund_msg,
                "whatsapp_link": f"https://wa.me/{order['customer_phone'].replace(' ', '').replace('+', '')}?text={urllib.parse.quote(wa_refund_msg)}",
                "message": f"Refund of ₹{refund_amount:.2f} processed successfully!"
            })
            return

        # 5. ADD DELIVERY PARTNER
        if path == "/api/delivery-partners":
            body = self.read_json_body()
            partner_id = f"dp-{uuid.uuid4().hex[:8]}"
            conn = get_db()
            conn.execute('''
            INSERT INTO delivery_partners (id, name, code, service_type, avg_days, tracking_url_pattern, contact_phone, rating, total_shipments, is_active, color, supports_auto_pickup)
            VALUES (?, ?, ?, ?, ?, ?, ?, 5.0, 0, 1, ?, ?)
            ''', (
                partner_id, body.get("name"), body.get("code", "EXPRESS").upper(),
                body.get("service_type", "Doorstep Pickup"), body.get("avg_days", "2-3 Days"),
                body.get("tracking_url_pattern", "https://track.courier.com/{TRACKING}"),
                body.get("contact_phone", "+91 90000 00000"),
                body.get("color", "#4F46E5"),
                1 if body.get("supports_auto_pickup", True) else 0
            ))
            conn.commit()
            conn.close()
            self.send_json({"success": True, "message": f"Courier partner '{body.get('name')}' added!"})
            return

        # 6. ADD PAYMENT METHOD
        if path == "/api/payment-methods":
            body = self.read_json_body()
            pm_id = f"pm-{uuid.uuid4().hex[:8]}"
            conn = get_db()
            conn.execute('''
            INSERT INTO payment_methods (id, name, provider, fee_percent, is_active, supported_types, upi_id)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            ''', (
                pm_id, body.get("name"), body.get("provider", "UPI"),
                float(body.get("fee_percent", 0.0)),
                body.get("supported_types", "UPI, QR, Cards"),
                body.get("upi_id", "")
            ))
            conn.commit()
            conn.close()
            self.send_json({"success": True, "message": f"Payment option '{body.get('name')}' added!"})
            return

        # 7. ADD DISCOUNT
        if path == "/api/discounts":
            body = self.read_json_body()
            disc_id = f"disc-{uuid.uuid4().hex[:8]}"
            conn = get_db()
            try:
                conn.execute('''
                INSERT INTO discounts (id, code, discount_type, value, min_order, usage_limit, times_used, expires_at, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, 1, ?)
                ''', (
                    disc_id, body.get("code", "PROMO").upper(),
                    body.get("discount_type", "percentage"),
                    float(body.get("value", 10.0)),
                    float(body.get("min_order", 0.0)),
                    int(body.get("usage_limit", 500)),
                    body.get("expires_at", "2026-12-31"),
                    datetime.now().strftime("%Y-%m-%d")
                ))
                conn.commit()
            except sqlite3.IntegrityError:
                conn.close()
                self.send_json({"error": "Discount code already exists"}, 400)
                return
            conn.close()
            self.send_json({"success": True, "message": f"Discount code '{body.get('code')}' created!"})
            return

        self.send_json({"error": "Endpoint not found"}, 404)

def run():
    init_db()
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    server_address = ('', PORT)
    httpd = socketserver.TCPServer(server_address, DashboardRequestHandler)
    print(f"🚀 Aura Commerce OS (WhatsApp & Courier Logistics) running at http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()

if __name__ == "__main__":
    run()
