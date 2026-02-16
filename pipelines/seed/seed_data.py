"""
Seed data generator — creates realistic e-commerce data in the raw schema.

Generates:
  - ~2 000 users
  - ~200 products (20 categories × 10 brands)
  - ~10 000 orders  (each with 1-5 line items)
  - ~50 000 sessions

All data is inserted via SQLAlchemy into the ``raw`` schema.
Run:  python -m pipelines.seed.seed_data
"""
from __future__ import annotations

import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from faker import Faker
from sqlalchemy import create_engine, text

# ── Load .env from project root ─────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

fake = Faker()
Faker.seed(42)
random.seed(42)

# ── Tunables ─────────────────────────────────────────────
NUM_USERS = 2_000
NUM_PRODUCTS = 200
NUM_ORDERS = 10_000
MAX_ITEMS_PER_ORDER = 5
NUM_SESSIONS = 50_000

COUNTRIES = ["India", "US", "UK", "Germany", "Canada", "Australia", "France", "Brazil", "Japan", "Nigeria"]
DEVICES = ["mobile", "desktop", "tablet"]
STATUSES = ["completed", "cancelled", "pending"]
STATUS_WEIGHTS = [0.70, 0.15, 0.15]
CURRENCIES = ["USD", "INR", "EUR", "GBP", "CAD", "AUD", "BRL", "JPY"]

CATEGORIES = [
    "Electronics", "Clothing", "Home & Kitchen", "Books", "Sports",
    "Beauty", "Toys", "Automotive", "Grocery", "Health",
    "Garden", "Pet Supplies", "Office", "Music", "Movies",
    "Software", "Baby", "Industrial", "Handmade", "Luggage",
]
BRANDS = [
    "AlphaGoods", "BetaBrand", "GammaTech", "DeltaWear", "EpsilonHome",
    "ZetaSport", "EtaBeauty", "ThetaPlay", "IotaAuto", "KappaFresh",
]

# ── Helper: date ranges ─────────────────────────────────
DATE_START = datetime(2024, 1, 1)
DATE_END = datetime(2025, 12, 31)
DATE_RANGE_DAYS = (DATE_END - DATE_START).days


def _rand_ts() -> datetime:
    return DATE_START + timedelta(
        days=random.randint(0, DATE_RANGE_DAYS),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )


def _db_url() -> str:
    user = os.getenv("POSTGRES_USER", "copilot")
    pw = os.getenv("POSTGRES_PASSWORD", "copilot_pw")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "analytics")
    return f"postgresql://{user}:{pw}@{host}:{port}/{db}"


# ── Generators ───────────────────────────────────────────

def gen_users() -> list[dict]:
    rows = []
    for uid in range(1, NUM_USERS + 1):
        rows.append({
            "user_id": uid,
            "signup_ts": _rand_ts(),
            "country": random.choice(COUNTRIES),
            "device": random.choice(DEVICES),
        })
    return rows


def gen_products() -> list[dict]:
    rows = []
    for pid in range(1, NUM_PRODUCTS + 1):
        rows.append({
            "product_id": pid,
            "category": CATEGORIES[(pid - 1) % len(CATEGORIES)],
            "brand": BRANDS[(pid - 1) % len(BRANDS)],
        })
    return rows


def gen_orders(users: list[dict]) -> tuple[list[dict], list[dict]]:
    """Returns (orders, order_items)."""
    user_ids = [u["user_id"] for u in users]
    orders: list[dict] = []
    items: list[dict] = []

    for oid in range(1, NUM_ORDERS + 1):
        uid = random.choice(user_ids)
        status = random.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
        order_ts = _rand_ts()
        currency = random.choice(CURRENCIES)
        orders.append({
            "order_id": oid,
            "user_id": uid,
            "order_ts": order_ts,
            "status": status,
            "currency": currency,
        })

        n_items = random.randint(1, MAX_ITEMS_PER_ORDER)
        product_ids_chosen = random.sample(range(1, NUM_PRODUCTS + 1), n_items)
        for pid in product_ids_chosen:
            items.append({
                "order_id": oid,
                "product_id": pid,
                "quantity": random.randint(1, 10),
                "unit_price": round(random.uniform(5.0, 500.0), 2),
            })

    return orders, items


def gen_sessions(users: list[dict]) -> list[dict]:
    user_ids = [u["user_id"] for u in users]
    rows = []
    for sid in range(1, NUM_SESSIONS + 1):
        uid = random.choice(user_ids)
        rows.append({
            "session_id": sid,
            "user_id": uid,
            "session_ts": _rand_ts(),
            "device": random.choice(DEVICES),
            "country": random.choice(COUNTRIES),
        })
    return rows


# ── Bulk insert helper ───────────────────────────────────

def _bulk_insert(engine, table: str, rows: list[dict], batch_size: int = 2000):
    """Insert rows into *table* in batches using executemany-style VALUES."""
    if not rows:
        return
    cols = list(rows[0].keys())
    col_list = ", ".join(cols)
    param_list = ", ".join(f":{c}" for c in cols)
    sql = text(f"INSERT INTO {table} ({col_list}) VALUES ({param_list}) ON CONFLICT DO NOTHING")
    with engine.begin() as conn:
        for i in range(0, len(rows), batch_size):
            conn.execute(sql, rows[i : i + batch_size])
    print(f"  ✓ {table}: {len(rows):,} rows")


# ── Main ─────────────────────────────────────────────────

def main():
    print("═══ Seed Data Generator ═══")
    engine = create_engine(_db_url(), echo=False)

    # Truncate existing data for idempotency
    print("Truncating raw tables …")
    with engine.begin() as conn:
        for t in [
            "raw.raw_order_items",
            "raw.raw_orders",
            "raw.raw_sessions",
            "raw.raw_users",
            "raw.raw_products",
        ]:
            conn.execute(text(f"TRUNCATE TABLE {t} CASCADE"))

    print("Generating data …")
    users = gen_users()
    products = gen_products()
    orders, items = gen_orders(users)
    sessions = gen_sessions(users)

    print("Inserting …")
    _bulk_insert(engine, "raw.raw_users", users)
    _bulk_insert(engine, "raw.raw_products", products)
    _bulk_insert(engine, "raw.raw_orders", orders)
    _bulk_insert(engine, "raw.raw_order_items", items)
    _bulk_insert(engine, "raw.raw_sessions", sessions)

    print(f"\nDone — seeded {len(users):,} users, {len(products):,} products, "
          f"{len(orders):,} orders, {len(items):,} items, {len(sessions):,} sessions.")


if __name__ == "__main__":
    main()
