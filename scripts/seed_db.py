#!/usr/bin/env python3
"""
Seed script for shop_db MySQL sample database.
Generates reproducible test data:
  - 50,000 customers
  - 2,000 products
  - 200,000 orders
  - 500,000 order items

Usage:
    python scripts/seed_db.py [--reset] [--scale 1.0] [--batch-size 5000]
"""

from __future__ import annotations

import argparse
import datetime
import os
import random
import sys
from urllib.parse import quote_plus

import sqlalchemy
from sqlalchemy import text

# Realistic seed dictionaries
FIRST_NAMES = [
    "James",
    "Mary",
    "John",
    "Patricia",
    "Robert",
    "Jennifer",
    "Michael",
    "Linda",
    "William",
    "Elizabeth",
    "David",
    "Barbara",
    "Richard",
    "Susan",
    "Joseph",
    "Jessica",
    "Thomas",
    "Sarah",
    "Charles",
    "Karen",
    "Christopher",
    "Nancy",
    "Daniel",
    "Lisa",
]
LAST_NAMES = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Hernandez",
    "Lopez",
    "Gonzalez",
    "Wilson",
    "Anderson",
    "Thomas",
    "Taylor",
    "Moore",
    "Jackson",
    "Martin",
    "Lee",
    "Perez",
    "Thompson",
    "White",
]
CITIES = [
    "New York",
    "Los Angeles",
    "Chicago",
    "Houston",
    "Phoenix",
    "Philadelphia",
    "San Antonio",
    "San Diego",
    "Dallas",
    "San Jose",
    "Austin",
    "Jacksonville",
    "San Francisco",
    "Columbus",
    "Indianapolis",
    "Fort Worth",
    "Charlotte",
    "Seattle",
]
STATES = ["NY", "CA", "IL", "TX", "AZ", "PA", "FL", "OH", "IN", "NC", "WA", "CO", "MI", "GA"]
CATEGORIES = [
    "Electronics",
    "Home & Garden",
    "Books",
    "Clothing",
    "Toys",
    "Sports",
    "Health",
    "Automotive",
]
STATUSES = ["COMPLETED", "PROCESSING", "SHIPPED", "PENDING", "CANCELLED", "REFUNDED"]
PAYMENTS = ["CREDIT_CARD", "DEBIT_CARD", "PAYPAL", "APPLE_PAY", "WIRE_TRANSFER"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed shop_db database with synthetic data.")
    parser.add_argument(
        "--reset", action="store_true", help="Drop and recreate shop_db before seeding."
    )
    parser.add_argument(
        "--scale", type=float, default=1.0, help="Scale factor (e.g. 0.05 for 5%% quick test)."
    )
    parser.add_argument("--batch-size", type=int, default=5000, help="Row count per batch INSERT.")
    return parser.parse_args()


def get_engine(database: str = "shop_db", root_connect: bool = False) -> sqlalchemy.engine.Engine:
    host = os.environ.get("DB_HOST", "localhost")
    port = int(os.environ.get("DB_PORT", "3306"))
    user = os.environ.get("DB_USER", "root")
    password = os.environ.get("DB_PASSWORD", "")
    db = "" if root_connect else database

    safe_user = quote_plus(user)
    safe_pass = quote_plus(password)
    db_path = f"/{quote_plus(db)}" if db else ""

    url = f"mysql+pymysql://{safe_user}:{safe_pass}@{host}:{port}{db_path}"
    return sqlalchemy.create_engine(url, pool_pre_ping=True)


def main() -> None:
    args = parse_args()
    db_target = os.environ.get("DB_DATABASE", "shop_db")

    # Safety check on reset
    if args.reset:
        if db_target.lower() != "shop_db":
            print(
                f"SECURITY GUARD: --reset is strictly restricted to 'shop_db'. Aborting against '{db_target}'."
            )
            sys.exit(1)

        print(f"Resetting database '{db_target}'...")
        root_engine = get_engine(root_connect=True)
        with root_engine.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS `{db_target}`"))
            conn.execute(
                text(
                    f"CREATE DATABASE `{db_target}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                )
            )
            conn.commit()
        root_engine.dispose()

        # Run schema DDL
        schema_file = os.path.join(os.path.dirname(__file__), "..", "sql", "schema.sql")
        if os.path.exists(schema_file):
            print("Applying sql/schema.sql...")
            engine = get_engine(database=db_target)
            with open(schema_file, "r", encoding="utf-8") as f:
                schema_sql = f.read()

            with engine.connect() as conn:
                for statement in schema_sql.split(";"):
                    stmt = statement.strip()
                    if (
                        stmt
                        and not stmt.upper().startswith("CREATE DATABASE")
                        and not stmt.upper().startswith("USE")
                    ):
                        conn.execute(text(stmt))
                conn.commit()
            engine.dispose()

    # Determine row counts based on scale factor
    num_customers = max(100, int(50_000 * args.scale))
    num_products = max(50, int(2_000 * args.scale))
    num_orders = max(200, int(200_000 * args.scale))
    num_items = max(500, int(500_000 * args.scale))

    print(f"Seeding shop_db (Scale: {args.scale:.2f}):")
    print(f"  • Customers:   {num_customers:,}")
    print(f"  • Products:    {num_products:,}")
    print(f"  • Orders:      {num_orders:,}")
    print(f"  • Order Items: {num_items:,}")

    rng = random.Random(42)
    engine = get_engine(database=db_target)

    start_time = datetime.datetime.now()

    # 1. Seed Customers
    print("Inserting customers...")
    cust_data = []
    base_date = datetime.datetime(2023, 1, 1)
    for i in range(1, num_customers + 1):
        fn = rng.choice(FIRST_NAMES)
        ln = rng.choice(LAST_NAMES)
        name = f"{fn} {ln}"
        email = f"{fn.lower()}.{ln.lower()}{i}@example.com"
        phone = f"555-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}"
        addr = f"{rng.randint(100, 9999)} {rng.choice(['Main', 'Oak', 'Pine', 'Maple', 'Elm'])} St"
        city = rng.choice(CITIES)
        state = rng.choice(STATES)
        zip_code = f"{rng.randint(10000, 99999)}"
        created = base_date + datetime.timedelta(
            days=rng.randint(0, 1000), seconds=rng.randint(0, 86400)
        )
        cust_data.append(
            {
                "name": name,
                "email": email,
                "phone": phone,
                "address": addr,
                "city": city,
                "state": state,
                "zip_code": zip_code,
                "created_at": created,
            }
        )

    with engine.connect() as conn:
        for offset in range(0, len(cust_data), args.batch_size):
            batch = cust_data[offset : offset + args.batch_size]
            conn.execute(
                text("""
                    INSERT INTO customers (name, email, phone, address, city, state, zip_code, created_at)
                    VALUES (:name, :email, :phone, :address, :city, :state, :zip_code, :created_at)
                """),
                batch,
            )
            conn.commit()
    print("✓ Customers inserted.")

    # 2. Seed Products
    print("Inserting products...")
    prod_data = []
    for i in range(1, num_products + 1):
        cat = rng.choice(CATEGORIES)
        sku = f"SKU-{cat[:3].upper()}-{i:06d}"
        name = f"{cat} Item #{i}"
        price = round(rng.uniform(5.0, 500.0), 2)
        cost = round(price * rng.uniform(0.3, 0.7), 2)
        qty = rng.randint(0, 1500)
        desc = f"Standard description for {name} in {cat} category with high-grade components."
        created = base_date + datetime.timedelta(days=rng.randint(0, 500))
        prod_data.append(
            {
                "sku": sku,
                "name": name,
                "category": cat,
                "price": price,
                "cost": cost,
                "stock_quantity": qty,
                "description": desc,
                "created_at": created,
            }
        )

    with engine.connect() as conn:
        for offset in range(0, len(prod_data), args.batch_size):
            batch = prod_data[offset : offset + args.batch_size]
            conn.execute(
                text("""
                    INSERT INTO products (sku, name, category, price, cost, stock_quantity, description, created_at)
                    VALUES (:sku, :name, :category, :price, :cost, :stock_quantity, :description, :created_at)
                """),
                batch,
            )
            conn.commit()
    print("✓ Products inserted.")

    # 3. Seed Orders
    print("Inserting orders...")
    order_data = []
    for i in range(1, num_orders + 1):
        cid = rng.randint(1, num_customers)
        odate = base_date + datetime.timedelta(
            days=rng.randint(0, 1200), seconds=rng.randint(0, 86400)
        )
        status = rng.choice(STATUSES)
        amt = round(rng.uniform(15.0, 2500.0), 2)
        pay = rng.choice(PAYMENTS)
        scity = rng.choice(CITIES)
        sstate = rng.choice(STATES)
        notes = f"Order #{i} standard packaging." if rng.random() > 0.5 else None
        order_data.append(
            {
                "customer_id": cid,
                "order_date": odate,
                "status": status,
                "total_amount": amt,
                "payment_method": pay,
                "shipping_city": scity,
                "shipping_state": sstate,
                "notes": notes,
            }
        )

    with engine.connect() as conn:
        for offset in range(0, len(order_data), args.batch_size):
            batch = order_data[offset : offset + args.batch_size]
            conn.execute(
                text("""
                    INSERT INTO orders (customer_id, order_date, status, total_amount, payment_method, shipping_city, shipping_state, notes)
                    VALUES (:customer_id, :order_date, :status, :total_amount, :payment_method, :shipping_city, :shipping_state, :notes)
                """),
                batch,
            )
            conn.commit()
    print("✓ Orders inserted.")

    # 4. Seed Order Items
    print("Inserting order items...")
    item_data = []
    for i in range(1, num_items + 1):
        oid = rng.randint(1, num_orders)
        pid = rng.randint(1, num_products)
        qty = rng.randint(1, 6)
        uprice = round(rng.uniform(10.0, 300.0), 2)
        discount = round(rng.uniform(0.0, uprice * 0.2), 2) if rng.random() > 0.7 else 0.00
        item_data.append(
            {
                "order_id": oid,
                "product_id": pid,
                "quantity": qty,
                "unit_price": uprice,
                "discount": discount,
            }
        )

    with engine.connect() as conn:
        for offset in range(0, len(item_data), args.batch_size):
            batch = item_data[offset : offset + args.batch_size]
            conn.execute(
                text("""
                    INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount)
                    VALUES (:order_id, :product_id, :quantity, :unit_price, :discount)
                """),
                batch,
            )
            conn.commit()
    print("✓ Order items inserted.")

    duration = (datetime.datetime.now() - start_time).total_seconds()
    print(f"\nDone! Seeded shop_db in {duration:.1f} seconds.")


if __name__ == "__main__":
    main()
