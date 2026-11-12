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
    # Verified products already published on Gumroad but absent from the current
    # storefront catalogue. Keeping these seeds is safe: existing complete
    # records are skipped on subsequent runs.
    "https://alshayebemad.gumroad.com/l/THECLOCKMAKERSDREAM",
    "https://alshayebemad.gumroad.com/l/APRAYERFORTOMORROW",
    "https://alshayebemad.gumroad.com/l/TheFirstLight",
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
        # Gumroad progressively renders product cards as the public profile is scrolled.
        # Continue until the number of unique product links stabilizes, rather than
        # sampling only the first viewport and silently missing later products.
        try:
            page.locator("a[href*='/l/']").first.wait_for(state="attached", timeout=15000)
        except Exception:
            pass
        previous_count = -1
        stable_rounds = 0
        for _ in range(40):
            current_links = page.locator("a[href*='/l/']").evaluate_all(
                "(els) => els.map(a => a.href).filter(Boolean)"
            )
            current_count = len({
                permalink_from_url(url) for url in current_links
                if permalink_from_url(url)
            })
            if current_count == previous_count:
                stable_rounds += 1
            else:
                stable_rounds = 0
            if stable_rounds >= 3:
                break
            previous_count = current_count
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(700)

        raw = page.locator("#gumroad-data").text_content() if page.locator("#gumroad-data").count() else None
        links = page.locator("a[href*='/l/']").evaluate_all(
            "(els) => els.map(a => a.href).filter(Boolean)"
        )
        browser.close()

    # Merge structured profile data with every public product link found after
    # scrolling. The structured payload may be paginated or stale; the visible
    # public links are an independent discovery source, not a fallback to discard.
    products_by_permalink = {}
    total = 0
    if raw:
        try:
            payload = find_catalog_payload(json.loads(raw or "{}"))
        except json.JSONDecodeError:
            payload = None
        if payload:
            for product in payload["products"]:
                permalink = product.get("permalink") or permalink_from_url(product.get("url", ""))
                if permalink:
                    products_by_permalink[permalink] = product
            total = int(payload.get("products_total", payload.get("productsTotal", len(products_by_permalink))))

    for url in links:
        permalink = permalink_from_url(url)
        if permalink:
            products_by_permalink.setdefault(
                permalink,
                {"permalink": permalink, "url": f"https://{STORE_HOST}/l/{permalink}"},
            )

    total = max(total, len(products_by_permalink))
    products = list(products_by_permalink.values())

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
    catalog_products = catalog.get("products", [])
    public_products, public_total = discover_public_products()

    def matching_catalog_product(discovered):
        permalink = discovered.get("permalink")
        discovered_path = urlparse(discovered.get("url", "")).path.rstrip("/").lower()
        return next(
            (
                product for product in catalog_products
                if product.get("permalink") == permalink
                or urlparse(product.get("url", "")).path.rstrip("/").lower() == discovered_path
            ),
            None,
        )

    # Revisit existing entries only when their full public description is missing.
    # This repairs older catalogue records once, without re-importing them forever.
    new_products = []
    for item in public_products:
        existing = matching_catalog_product(item)
        if existing is None or not existing.get("full_description"):
            new_products.append(item)
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

    catalog_after = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    catalog_after_products = catalog_after.get("products", [])

    # The URL slug visible on a public Gumroad page is not always the
    # canonical product permalink stored in Gumroad metadata. Resolve every
    # refreshed/imported item against the post-import catalogue by URL path,
    # then report the canonical catalogue permalink for downstream checks.
    imported = []
    for item in new_products:
        item_path = urlparse(item.get("url", "")).path.rstrip("/").lower()
        matched = next(
            (
                product for product in catalog_after_products
                if product.get("permalink") == item.get("permalink")
                or urlparse(product.get("url", "")).path.rstrip("/").lower() == item_path
            ),
            None,
        )
        if matched and matched.get("permalink"):
            imported.append(matched["permalink"])

    catalog_after_permalinks = {
        str(product.get("permalink", "")).strip().lower()
        for product in catalog_after_products
        if product.get("permalink")
    }
    catalog_after_paths = {
        urlparse(product.get("url", "")).path.rstrip("/").lower()
        for product in catalog_after_products
        if product.get("url")
    }
    unmatched_after_import = [
        item.get("permalink")
        for item in public_products
        if str(item.get("permalink", "")).strip().lower() not in catalog_after_permalinks
        and urlparse(item.get("url", "")).path.rstrip("/").lower() not in catalog_after_paths
    ]
    discovery_complete = public_total <= len(public_products) or public_total == 0
    report = {
        "profile_url": PROFILE_URL,
        "public_products_total": public_total,
        "public_products_discovered": len(public_products),
        "catalog_products_before": len(known),
        "new_products_discovered": len(new_products),
        "new_products_imported": imported,
        "catalog_products_after": len(catalog_after_products),
        "discovery_complete": discovery_complete,
        "unmatched_public_products_after_import": unmatched_after_import,
        "status": "imported" if imported else "no_new_products",
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if not discovery_complete:
        raise RuntimeError(
            f"Public Gumroad discovery was incomplete: expected at least {public_total} products, "
            f"found {len(public_products)}. See {REPORT_PATH}."
        )
    if unmatched_after_import:
        raise RuntimeError(
            "Published Gumroad products remain absent from the storefront catalogue: "
            + ", ".join(map(str, unmatched_after_import))
        )
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
