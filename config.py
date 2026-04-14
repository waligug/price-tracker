import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHARTS_DIR = os.path.join(BASE_DIR, "charts")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")
PRICES_CSV = os.path.join(DATA_DIR, "prices.csv")

STORE_CONFIGS = {
    "memoryexpress": {
        "url_pattern": re.compile(r"memoryexpress\.com"),
        "price_selector": ".GrandTotal",
        "name_selector": ".c-capr-header__title",
        "wait_for": ".GrandTotal",
        "cloudflare": True,
    },
    "amazon_ca": {
        "url_pattern": re.compile(r"amazon\.ca"),
        "price_selector": ".a-price .a-offscreen",
        "name_selector": "#productTitle",
        "wait_for": ".a-price",
        "cloudflare": False,
    },
    "newegg": {
        "url_pattern": re.compile(r"newegg\.ca"),
        "price_selector": ".price-current",
        "name_selector": ".product-title",
        "wait_for": ".price-current",
        "cloudflare": False,
    },
    "canadacomputers": {
        "url_pattern": re.compile(r"canadacomputers\.com"),
        "price_selector": ".price-show-sell span",
        "name_selector": ".page-product_info h1",
        "wait_for": ".price-show-sell",
        "cloudflare": False,
    },
}


def detect_store(url):
    for store_name, cfg in STORE_CONFIGS.items():
        if cfg["url_pattern"].search(url):
            return store_name
    return None
