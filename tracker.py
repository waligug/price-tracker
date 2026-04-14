"""Main orchestrator: scrape -> save CSV -> generate JSONs -> charts -> commit+push."""

import argparse
import csv
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime

from config import DATA_DIR, CHARTS_DIR, LOGS_DIR, PRODUCTS_FILE, PRICES_CSV, BASE_DIR
from scraper import scrape_all, fetch_product_name
from charts import generate_charts
from cli import load_products as cli_load_products, save_products, slugify

PENDING_FILE = os.path.join(DATA_DIR, "pending.txt")


def load_products():
    if not os.path.exists(PRODUCTS_FILE):
        print("No products.json found. Add products with: python cli.py add <url>")
        sys.exit(1)
    with open(PRODUCTS_FILE) as f:
        return json.load(f)


def process_pending():
    """Process pending product URLs queued from GitHub UI."""
    if not os.path.exists(PENDING_FILE):
        return

    with open(PENDING_FILE) as f:
        urls = [line.strip() for line in f if line.strip()]

    if not urls:
        os.remove(PENDING_FILE)
        return

    print(f"Processing {len(urls)} pending product(s)...")
    products = cli_load_products()
    existing_urls = {p["url"] for p in products}
    existing_ids = {p["id"] for p in products}
    added = 0

    for url in urls:
        if url in existing_urls:
            print(f"  Already tracking: {url}")
            continue

        store = None
        from config import detect_store
        store = detect_store(url)
        if not store:
            print(f"  Unknown store, skipping: {url}")
            continue

        print(f"  Fetching name for: {url}")
        name = fetch_product_name(url)
        if not name:
            print(f"  Could not fetch name, skipping: {url}")
            continue

        product_id = slugify(name)
        base_id = product_id
        counter = 2
        while product_id in existing_ids:
            product_id = f"{base_id}-{counter}"
            counter += 1

        products.append({
            "id": product_id,
            "name": name,
            "url": url,
            "store": store,
        })
        existing_ids.add(product_id)
        existing_urls.add(url)
        added += 1
        print(f"  Added: {name} ({product_id})")

    save_products(products)
    os.remove(PENDING_FILE)
    print(f"  Processed pending queue: {added} new product(s)\n")


def save_prices(results):
    """Append new prices to CSV."""
    os.makedirs(DATA_DIR, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")

    # Read existing entries for today to avoid duplicates
    today_entries = set()
    if os.path.exists(PRICES_CSV):
        with open(PRICES_CSV, newline="") as f:
            for row in csv.reader(f):
                if len(row) >= 2 and row[0] == date:
                    today_entries.add(row[1])

    write_header = not os.path.exists(PRICES_CSV)
    with open(PRICES_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["date", "product_id", "price"])
        for product_id, price in results:
            if product_id in today_entries:
                print(f"  Already have today's price for {product_id}, skipping")
                continue
            writer.writerow([date, product_id, f"{price:.2f}"])


def load_price_history():
    """Load all price history from CSV into a dict of {product_id: [(date, price), ...]}."""
    history = defaultdict(list)
    if not os.path.exists(PRICES_CSV):
        return history
    with open(PRICES_CSV, newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            if len(row) >= 3:
                history[row[1]].append((row[0], float(row[2])))
    return history


def generate_product_jsons(products):
    """Regenerate per-product JSON files from CSV for the GitHub Pages dashboard."""
    history = load_price_history()
    product_map = {p["id"]: p for p in products}

    for pid, entries in history.items():
        p = product_map.get(pid, {})
        data = {
            "id": pid,
            "name": p.get("name", pid),
            "url": p.get("url", ""),
            "site": p.get("store", ""),
            "history": [{"date": d, "price": pr} for d, pr in entries],
        }
        path = os.path.join(DATA_DIR, f"{pid}.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


def generate_readme(products):
    """Generate README.md with current prices table and chart images."""
    history = load_price_history()
    product_map = {p["id"]: p for p in products}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "# Price Tracker",
        "",
        f"Last updated: {now}",
        "",
        "## Current Prices",
        "",
        "| Product | Store | Current | 7d Change | All-Time Low |",
        "|---------|-------|---------|-----------|--------------|",
    ]

    for p in products:
        pid = p["id"]
        entries = history.get(pid, [])
        if not entries:
            continue

        current_price = entries[-1][1]
        all_time_low = min(pr for _, pr in entries)

        # 7-day change: find the most recent price from 7+ days ago
        from datetime import timedelta
        cutoff_str = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        seven_days_ago = None
        for d, pr in entries:
            if d <= cutoff_str:
                seven_days_ago = pr  # keeps getting overwritten, so we get the latest one <= 7d ago
        if seven_days_ago is not None and seven_days_ago != 0:
            change = ((current_price - seven_days_ago) / seven_days_ago) * 100
            change_str = f"{change:+.1f}%"
        else:
            change_str = "—"

        store = p.get("store", "?")
        lines.append(
            f"| [{p['name']}]({p['url']}) | {store} | ${current_price:.2f} | {change_str} | ${all_time_low:.2f} |"
        )

    lines.append("")
    lines.append("## Price History")
    lines.append("")

    for p in products:
        pid = p["id"]
        chart_path = f"charts/{pid}.png"
        if os.path.exists(os.path.join(BASE_DIR, chart_path)):
            lines.append(f"### {p['name']}")
            lines.append(f"![Price History]({chart_path})")
            lines.append("")

    readme_path = os.path.join(BASE_DIR, "README.md")
    with open(readme_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Updated README.md")


def git_commit_and_push():
    """Stage data/charts/README, commit if changes exist, push."""
    os.chdir(BASE_DIR)

    subprocess.run(["git", "add", "data/", "charts/", "README.md"], check=True)

    result = subprocess.run(["git", "diff", "--staged", "--quiet"])
    if result.returncode == 0:
        print("  No price changes, skipping commit.")
        return

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    subprocess.run(
        ["git", "commit", "-m", f"Update prices {date_str}"],
        check=True,
    )

    # Pull rebase first to handle conflicts with GitHub Actions
    subprocess.run(["git", "pull", "--rebase"], check=False)
    subprocess.run(["git", "push"], check=True)
    print("  Committed and pushed.")


def main():
    parser = argparse.ArgumentParser(description="Price Tracker")
    parser.add_argument("--skip-cloudflare", action="store_true",
                        help="Skip stores with Cloudflare protection (for GitHub Actions)")
    parser.add_argument("--no-push", action="store_true",
                        help="Don't git commit/push after scraping")
    args = parser.parse_args()

    # Pull latest to pick up any pending.txt from GitHub UI
    if not args.no_push:
        os.chdir(BASE_DIR)
        subprocess.run(["git", "pull", "--rebase"], check=False)

    process_pending()

    products = load_products()
    print(f"Tracking {len(products)} product(s)...\n")

    print("Scraping prices...")
    results = scrape_all(products, skip_cloudflare=args.skip_cloudflare)

    if not results:
        print("\nNo prices scraped. Nothing to save.")
        return

    print("\nSaving prices...")
    save_prices(results)

    print("Generating product JSONs...")
    generate_product_jsons(products)

    print("Generating charts...")
    os.makedirs(CHARTS_DIR, exist_ok=True)
    history = load_price_history()
    product_map = {p["id"]: p for p in products}
    generate_charts(history, product_map, CHARTS_DIR)

    print("Generating README...")
    generate_readme(products)

    if not args.no_push:
        print("Committing and pushing...")
        git_commit_and_push()

    print("\nDone!")


if __name__ == "__main__":
    main()
