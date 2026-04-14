import random
import re
import time
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from config import STORE_CONFIGS, detect_store

stealth = Stealth()


def scrape_all(products, skip_cloudflare=False):
    """Scrape prices for all products. Returns list of (product_id, price) tuples."""
    results = []
    errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        stealth.apply_stealth_sync(context)

        for i, product in enumerate(products):
            store = detect_store(product["url"])
            if not store:
                errors.append((product["id"], f"Unknown store for URL: {product['url']}"))
                continue

            cfg = STORE_CONFIGS[store]

            if skip_cloudflare and cfg.get("cloudflare"):
                print(f"  Skipping {product['name']} (Cloudflare, --skip-cloudflare)")
                continue

            print(f"  Scraping: {product['name']}")
            print(f"    URL: {product['url']}")

            try:
                page = context.new_page()

                page.goto(product["url"], wait_until="networkidle", timeout=30000)

                # Extra wait for Cloudflare-protected sites
                if cfg.get("cloudflare"):
                    time.sleep(random.uniform(2, 4))

                # Try the configured selector
                price_text = None
                try:
                    page.wait_for_selector(cfg["wait_for"], timeout=10000)
                    el = page.query_selector(cfg["price_selector"])
                    if el:
                        price_text = el.text_content().strip()
                        print(f"    Matched selector: {cfg['price_selector']}")
                except Exception:
                    pass

                # Fallback: scan page for dollar amounts
                if not price_text:
                    price_text = page.evaluate("""() => {
                        const els = document.querySelectorAll('*');
                        for (const el of els) {
                            if (el.children.length === 0) {
                                const t = el.textContent.trim();
                                if (/^\\$[\\d,]+(\\.[\\d]{2})?$/.test(t)) return t;
                            }
                        }
                        return null;
                    }""")
                    if price_text:
                        print(f"    Found price via fallback scan")

                page.close()

                if not price_text:
                    errors.append((product["id"], "No price found on page"))
                    print(f"    WARNING: No price found")
                    continue

                # Parse: "$1,299.99" -> 1299.99
                price = float(re.sub(r"[^\d.]", "", price_text))
                print(f"    Price: ${price:.2f}")
                results.append((product["id"], price))

            except Exception as e:
                errors.append((product["id"], str(e)))
                print(f"    ERROR: {e}")

            # Polite delay between products
            if i < len(products) - 1:
                delay = random.uniform(3, 5)
                time.sleep(delay)

        browser.close()

    if errors:
        print(f"\n  {len(errors)} error(s):")
        for pid, msg in errors:
            print(f"    {pid}: {msg}")

    return results


def fetch_product_name(url):
    """Fetch the product name from a URL by scraping the page title."""
    store = detect_store(url)
    if not store:
        return None

    cfg = STORE_CONFIGS[store]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )
        stealth.apply_stealth_sync(context)
        page = context.new_page()

        page.goto(url, wait_until="networkidle", timeout=30000)

        if cfg.get("cloudflare"):
            time.sleep(random.uniform(2, 4))

        name = None
        try:
            el = page.query_selector(cfg["name_selector"])
            if el:
                name = el.text_content().strip()
        except Exception:
            pass

        if not name:
            name = page.title().split("|")[0].split("-")[0].strip()

        browser.close()
        return name
