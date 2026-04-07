"""
Seed plumbing products (A–Z) into Supabase `products` table.

Usage (from BACKEND folder):
  python scripts/seed_products.py

Prerequisites:
  - Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
    (or `SUPABASE_ANON_KEY`) in environment
  - Create the `products` table in Supabase. Example SQL is printed if
    insert fails.

This script will attempt to upsert the JSON data bundled in
`data/products_a_to_z.json`.
"""
import json
import os
import sys
from pathlib import Path

# Ensure BACKEND is on sys.path so we can import app.extensions
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.extensions import supabase


def load_products():
    data_file = ROOT / "data" / "products_a_to_z.json"
    with open(data_file, "r", encoding="utf-8") as fh:
        return json.load(fh)


def ensure_env():
    missing = []
    if not os.getenv("SUPABASE_URL"):
        missing.append("SUPABASE_URL")
    if not (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")):
        missing.append("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY")
    if missing:
        print("Missing environment variables:", ", ".join(missing))
        return False
    return True


def main():
    if not ensure_env():
        print("Set the required env vars and re-run the script.")
        return 2

    if supabase is None:
        print("Supabase client not configured (check env vars). Exiting.")
        return 3

    products = load_products()
    print(f"Loaded {len(products)} products; attempting upsert into Supabase 'products' table...")

    try:
        resp = supabase.table("products").upsert(products).execute()
        if getattr(resp, "error", None):
            print("Supabase returned error:", resp.error)
            raise RuntimeError(resp.error)
        data = getattr(resp, "data", []) or []
        print("Upsert completed. Response size:", len(data))
        return 0
    except Exception as exc:
        print("Failed to write to Supabase. Error:", exc)
        print()
        print("If the `products` table does not exist in your Supabase")
        print("project, run the following SQL in the Supabase SQL editor:")
        print("--- SQL to run ---")
        print("CREATE TABLE products (")
        print("  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),")
        print("  sku TEXT UNIQUE,")
        print("  name TEXT NOT NULL,")
        print("  category TEXT,")
        print("  price NUMERIC,")
        print("  unit TEXT,")
        print("  description TEXT,")
        print("  created_at TIMESTAMPTZ DEFAULT now()")
        print(");")
        print("--- End SQL ---")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
