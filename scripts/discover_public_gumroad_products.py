#!/usr/bin/env python3
"""Discover public Gumroad products and import new items without OAuth.

Gumroad's public profile no longer consistently exposes the legacy #gumroad-data
node. Prefer that structured payload when available; otherwise fall back to public
product links rendered on the profile and explicitly supplied one-time seed URLs.
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright

PROFILE_URL = "https://alshayebemad.gumroad.com/"
STORE_HOST = "alshayebemad.gumroad.com"
# One-time bootstrap for the newly published product supplied by the store owner.
SEED_PRODUCT_URLS = [
    "https://alshayebemad.gumroad.com/l/THECLOCKMAKERSDREAM",
]
CATALOG_PATH = Path("catalog-data.json")
REPORT_PATH = Path("public-gumroad-discovery-report.json")

def find_catalog_payload(value):
    if isinstance(value, dict):
        if isinstance(value.get("products"), list) and (
            "products_total" in value or "posts_total" in value or "productsTotal" in value
        ):
            return value
        for child in value.values():
            found = find_catalog_payload(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_catalog_payload(child)
            if found:
                return found
    return None

def permalink_from_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != STORE_HOST:
        return None
    match = re.fullmatch(r"/l/([^/]+)/?", parsed.path)
    return match.group(1) if match else None

def discover_public_products():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        response = page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
        if response is not None and response.status >= 400:
            browser.close()
            raise RuntimeError(f"Public Gumroad profile returned HTTP {response.status}")
        # Give the public profile a short opportunity to render its product cards.
        try:
            page.locator("a[href*='/l/']").first.wait_for(state="attached", timeout=15000)
        except Exception:
            pass
        raw = page.locator("#gumroad-data").text_content() if page.locator("#gumroad-data").count() else None
        links = page.locator("a[href*='/l/']").evaluate_all(
            "(els) => els.map(a => a.href).filter(Boolean)"
        )
        browser.close()

    products = []
    total = 0
    if raw:
        try:
            payload = find_catalog_payload(json.loads(raw or "{}"))
        except json.JSONDecodeError:
            payload = None
        if payload:
            products = list(payload["products"])
            total = int(payload.get("products_total", payload.get("productsTotal", len(products))))
    # Fallback for Gumroad's current public profile rendering, which exposes product links
    # but may omit the old #gumroad-data catalogue element.
    if not products:
        seen_urls = set()
        for url in links:
            permalink = permalink_from_url(url)
            canonical = f"https://{STORE_HOST}/l/{permalink}" if permalink else None
            if canonical and canonical not in seen_urls:
                products.append({"permalink": permalink, "url": canonical})
                seen_urls.add(canonical)
        total = len(products)

    for url in SEED_PRODUCT_URLS:
        permalink = permalink_from_url(url)
        if not permalink:
            raise RuntimeError(f"Refusing invalid seeded product URL: {url}")
        if not any(p.get("permalink") == permalink for p in products):
            products.append({"permalink": permalink, "url": url})
    unique = {}
    for product in products:
        permalink = product.get("permalink")
        if permalink:
            unique[permalink] = product
    return list(unique.values()), total

def main():
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    known = {p.get("permalink") for p in catalog.get("products", [])}
    public_products, public_total = discover_public_products()
    new_products = [p for p in public_products if p.get("permalink") not in known]
    imported = []
    for item in new_products:
        permalink = item["permalink"]
        url = item.get("url") or f"https://{STORE_HOST}/l/{permalink}"
        if not url.startswith(f"https://{STORE_HOST}/l/"):
            raise RuntimeError(f"Refusing non-storefront product URL for {permalink}: {url}")
        print(f"DISCOVERED_NEW_PUBLIC_PRODUCT: {permalink} | {item.get('name', '')}", flush=True)
        subprocess.run(
            [sys.executable, "scripts/import_public_gumroad_product.py", "--url", url],
            check=True,
        )
        imported.append(permalink)

    report = {
        "profile_url": PROFILE_URL,
        "public_products_total": public_total,
        "public_products_discovered": len(public_products),
        "catalog_products_before": len(known),
        "new_products_discovered": len(new_products),
        "new_products_imported": imported,
        "status": "imported" if imported else "no_new_products",
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if imported:
        print("PUBLIC_GUMROAD_DISCOVERY_IMPORT_OK", flush=True)
    else:
        print("NO_NEW_PRODUCTS_FOUND", flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"PUBLIC_GUMROAD_DISCOVERY_FAILED: {exc}", file=sys.stderr)
        raise
