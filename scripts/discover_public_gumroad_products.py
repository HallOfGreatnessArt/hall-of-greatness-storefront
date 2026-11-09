#!/usr/bin/env python3
"""Discover newly published products from the public Gumroad profile and import them without OAuth."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

PROFILE_URL = "https://alshayebemad.gumroad.com/"
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

def discover_public_products():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        response = page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
        page.locator("#gumroad-data").wait_for(state="attached", timeout=30000)
        raw = page.locator("#gumroad-data").text_content()
        browser.close()
    if response is not None and response.status >= 400:
        raise RuntimeError(f"Public Gumroad profile returned HTTP {response.status}")
    payload = find_catalog_payload(json.loads(raw or "{}"))
    if not payload:
        raise RuntimeError("Could not find the documented #gumroad-data catalogue payload")
    products = list(payload["products"])
    total = int(payload.get("products_total", payload.get("productsTotal", len(products))))
    offset = len(products)
    # Gumroad profile pages expose the newest 100 products initially. Page safely if the
    # public profile reports more; do not silently mistake a partial list for a full scan.
    while offset < total:
        batch = page_more_products(offset)
        if not batch:
            raise RuntimeError(f"Public profile pagination stopped at {offset} of {total} products")
        products.extend(batch)
        offset += len(batch)
    if len(products) < total:
        raise RuntimeError(f"Incomplete public catalogue: found {len(products)} of {total}")
    unique = {}
    for product in products:
        permalink = product.get("permalink")
        if permalink:
            unique[permalink] = product
    return list(unique.values()), total

def page_more_products(offset):
    # A separate browser session uses Gumroad's documented public-profile pagination bridge.
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
        page.locator("#gumroad-data").wait_for(state="attached", timeout=30000)
        result = page.evaluate("""async (offset) => {
          if (!window.gumroadProducts?.request) throw new Error("Gumroad public pagination bridge unavailable");
          const result = await window.gumroadProducts.request({offset, limit: 100});
          if (!result?.success) throw new Error("Gumroad public pagination request failed");
          return result.products || [];
        }""", offset)
        browser.close()
        return result

def main():
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    known = {p.get("permalink") for p in catalog.get("products", [])}
    public_products, public_total = discover_public_products()
    new_products = [p for p in public_products if p.get("permalink") not in known]
    imported = []
    for item in new_products:
        permalink = item["permalink"]
        url = item.get("url") or f"https://alshayebemad.gumroad.com/l/{permalink}"
        if not url.startswith("https://alshayebemad.gumroad.com/l/"):
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
