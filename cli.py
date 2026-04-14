"""CLI for managing tracked products."""

import argparse
import json
import os
import re
import sys

from config import PRODUCTS_FILE, DATA_DIR, detect_store


def load_products():
    if not os.path.exists(PRODUCTS_FILE):
        return []
    with open(PRODUCTS_FILE) as f:
        return json.load(f)


def save_products(products):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PRODUCTS_FILE, "w") as f:
        json.dump(products, f, indent=2)


def slugify(text):
    """Turn text into a URL-safe ID."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60].strip("-")


def cmd_add(args):
    url = args.url.strip()
    store = detect_store(url)
    if not store:
        print(f"Error: Could not detect store for URL: {url}")
        print("Supported stores: memoryexpress, amazon_ca, newegg, canadacomputers")
        sys.exit(1)

    products = load_products()

    # Check for duplicate URL
    for p in products:
        if p["url"] == url:
            print(f"Already tracking: {p['name']} ({p['id']})")
            return

    # Get product name
    name = args.name
    if not name:
        print(f"Fetching product name from {store}...")
        from scraper import fetch_product_name
        name = fetch_product_name(url)
        if not name:
            print("Could not auto-detect name. Use --name to provide one.")
            sys.exit(1)
        print(f"  Found: {name}")

    product_id = slugify(name)

    # Ensure unique ID
    existing_ids = {p["id"] for p in products}
    base_id = product_id
    counter = 2
    while product_id in existing_ids:
        product_id = f"{base_id}-{counter}"
        counter += 1

    product = {
        "id": product_id,
        "name": name,
        "url": url,
        "store": store,
    }
    products.append(product)
    save_products(products)
    print(f"Added: {name}")
    print(f"  ID:    {product_id}")
    print(f"  Store: {store}")
    print(f"  URL:   {url}")


def cmd_remove(args):
    products = load_products()
    original_len = len(products)
    products = [p for p in products if p["id"] != args.id]

    if len(products) == original_len:
        print(f"No product found with ID: {args.id}")
        sys.exit(1)

    save_products(products)
    print(f"Removed: {args.id}")
    if not args.keep_history:
        print("  Price history kept in CSV. Use --no-keep-history to discuss removal.")


def cmd_list(args):
    products = load_products()
    if not products:
        print("No products tracked. Add one with: python cli.py add <url>")
        return

    print(f"Tracking {len(products)} product(s):\n")
    for p in products:
        print(f"  {p['id']}")
        print(f"    {p['name']}")
        print(f"    {p['store']} | {p['url']}")
        print()


def cmd_scrape(args):
    """Manual one-off scrape."""
    from tracker import main as tracker_main
    sys.argv = ["tracker.py", "--no-push"]
    if args.dry_run:
        print("Dry run mode - would scrape these products:")
        products = load_products()
        for p in products:
            print(f"  {p['name']} ({p['store']})")
        return
    tracker_main()


def main():
    parser = argparse.ArgumentParser(description="Price Tracker CLI")
    subs = parser.add_subparsers(dest="command", required=True)

    # add
    add_p = subs.add_parser("add", help="Add a product to track")
    add_p.add_argument("url", help="Product URL")
    add_p.add_argument("--name", help="Product name (auto-detected if omitted)")
    add_p.set_defaults(func=cmd_add)

    # remove
    rm_p = subs.add_parser("remove", help="Remove a tracked product")
    rm_p.add_argument("id", help="Product ID")
    rm_p.add_argument("--keep-history", action="store_true", default=True)
    rm_p.set_defaults(func=cmd_remove)

    # list
    ls_p = subs.add_parser("list", help="List tracked products")
    ls_p.set_defaults(func=cmd_list)

    # scrape
    sc_p = subs.add_parser("scrape", help="Run a manual scrape")
    sc_p.add_argument("--dry-run", action="store_true", help="Show what would be scraped")
    sc_p.set_defaults(func=cmd_scrape)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
