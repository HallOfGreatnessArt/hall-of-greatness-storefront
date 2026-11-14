#!/usr/bin/env python3
"""Responsive, image-loading, accessibility and SEO smoke tests for the storefront."""
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from functools import partial

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "catalog-data.json").read_text(encoding="utf-8"))
PUBLISHED = [p for p in CATALOG["products"] if p.get("published")]
HOME_WIDTHS = [320, 360, 375, 390, 414, 430, 768, 1024, 1280, 1440, 1920]
PRODUCT_WIDTHS = [320, 390, 768, 1024, 1440]
FAILURES = []
IMAGE_FAILURES = []
PAGE_COUNT = 0

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

def record(condition, message):
    if not condition:
        FAILURES.append(message)

def inspect_page(page, path, widths, expected_product=False):
    global PAGE_COUNT
    PAGE_COUNT += 1
    response = page.goto(f"http://127.0.0.1:8765/{path}", wait_until="domcontentloaded", timeout=30000)
    record(response is not None and response.status == 200, f"{path}: HTTP response was not 200")

    page.wait_for_timeout(350)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    # Give lazy-loaded CDN artwork a short, bounded window to finish after scrolling.
    page.wait_for_timeout(1800)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(150)

    metadata = page.evaluate("""() => ({
      title: document.title.trim(),
      description: document.querySelector('meta[name="description"]')?.content?.trim() || '',
      canonical: document.querySelector('link[rel="canonical"]')?.href || '',
      images: [...document.images].map(i => ({
        src: i.currentSrc || i.src,
        alt: (i.getAttribute('alt') || '').trim(),
        loaded: i.complete && i.naturalWidth > 0,
        width: i.naturalWidth,
        height: i.naturalHeight
      }))
    })""")
    record(bool(metadata["title"]), f"{path}: missing document title")
    record(bool(metadata["description"]), f"{path}: missing meta description")
    record(bool(metadata["canonical"]), f"{path}: missing canonical URL")
    record(page.locator('link[rel="canonical"]').count() == 1,
           f"{path}: expected exactly one canonical link")
    for image in metadata["images"]:
        record(bool(image["alt"]), f"{path}: image missing alt text: {image['src']}")
        if not image["loaded"]:
            IMAGE_FAILURES.append(f"{path}: image failed to load: {image['src']}")

    if expected_product:
        schema = page.locator('script#product-jsonld').count()
        record(schema == 1, f"{path}: expected exactly one Product JSON-LD block")
        if schema == 1:
            try:
                parsed_schema = json.loads(page.locator('script#product-jsonld').inner_text())
                record(parsed_schema.get("@type") == "Product", f"{path}: invalid Product structured data")
            except (ValueError, TypeError):
                record(False, f"{path}: Product structured data is not valid JSON")
        og_url = page.locator('meta[property="og:url"]')
        record(og_url.count() == 1, f"{path}: expected exactly one Open Graph canonical URL")
        if og_url.count() == 1:
            record(og_url.get_attribute("content") == metadata["canonical"],
                   f"{path}: Open Graph URL does not match canonical URL")
        for name in ("twitter:card", "twitter:title", "twitter:description", "twitter:image"):
            record(page.locator(f'meta[name="{name}"]').count() == 1,
                   f"{path}: expected exactly one {name} metadata tag")

    for width in widths:
        page.set_viewport_size({"width": width, "height": 900 if width >= 768 else 844})
        page.wait_for_timeout(60)
        dimensions = page.evaluate("""() => ({
          viewport: document.documentElement.clientWidth,
          scroll: document.documentElement.scrollWidth,
          body: document.body.scrollWidth
        })""")
        record(
            dimensions["scroll"] <= dimensions["viewport"] + 1
            and dimensions["body"] <= dimensions["viewport"] + 1,
            f"{path}: horizontal overflow at {width}px "
            f"(viewport={dimensions['viewport']}, scroll={dimensions['scroll']}, body={dimensions['body']})"
        )

def main():
    handler = partial(QuietHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 8765), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
            # Mock product destinations so the test verifies exact URLs without
            # depending on Gumroad's live page rendering or anti-bot checks.
            context.route(
                "https://alshayebemad.gumroad.com/l/**",
                lambda route: route.fulfill(
                    status=200,
                    content_type="text/html",
                    body="<html><head><title>Mock Gumroad destination</title></head><body>OK</body></html>",
                ),
            )
            page = context.new_page()
            page.set_default_timeout(10000)
            inspect_page(page, "index.html", HOME_WIDTHS, expected_product=False)
            home_cards = page.locator("#works .work").count()
            expected_works = len([x for x in PUBLISHED if not x.get("is_bundle")])
            # Verify bounded automatic retries, a visible recovery state, and
            # a successful user-triggered retry without changing the catalogue.
            failures_remaining = {"count": 2, "intercepted": 0}
            def fail_catalog_twice(route):
                failures_remaining["intercepted"] += 1
                if failures_remaining["count"] > 0:
                    failures_remaining["count"] -= 1
                    route.abort("failed")
                else:
                    route.continue_()
            # Use a page-scoped regex route to make the simulated failure
            # deterministic even when the cache-busting query string changes.
            import re
            catalog_route = re.compile(r".*/catalog-data\.json(?:\?.*)?$")
            page.route(catalog_route, fail_catalog_twice)
            page.reload(wait_until="domcontentloaded")
            page.locator("#retry-catalog").wait_for(state="visible", timeout=15000)
            record(failures_remaining["intercepted"] >= 2,
                   "The simulated catalogue network failure did not intercept both automatic attempts")
            record(page.locator("#bundles .catalog-status").count() == 1,
                   "Catalogue failure did not show a collection status message")
            page.locator("#retry-catalog").click()
            page.locator("#works .work").first.wait_for(state="attached", timeout=15000)
            record(page.locator("#works .work").count() == expected_works,
                   "Manual retry did not restore the published artwork cards")
            expected_bundle_count = len([x for x in PUBLISHED if x.get("is_bundle")])
            record(page.locator("#bundles .bundle").count() == expected_bundle_count,
                   "Manual retry did not restore the published collection cards")
            page.unroute(catalog_route, fail_catalog_twice)
            record(page.evaluate("validProductUrl('https://alshayebemad.gumroad.com/l/safe-item')") is True,
                   "Valid Gumroad product URL was rejected")
            record(page.evaluate("validProductUrl('javascript:alert(1)')") is False,
                   "Unsafe product URL was not rejected")
            record(page.evaluate("validCoverUrl('https://public-files.gumroad.com/example')") is True,
                   "Valid Gumroad cover URL was rejected")
            record(page.evaluate("validCoverUrl('https://example.com/image.jpg')") is False,
                   "Untrusted cover URL was not rejected")
            record(home_cards == expected_works,
                   f"Homepage gallery rendered {home_cards} artwork cards; expected {expected_works}")
            navigable_cards = page.locator("#works .work[data-store-url]")
            record(navigable_cards.count() == expected_works,
                   "One or more artwork cards are missing their full-card Gumroad destination")
            expected_bundles = len([x for x in PUBLISHED if x.get("is_bundle")])
            bundle_cards = page.locator("#bundles .bundle[data-store-url]")
            record(bundle_cards.count() == expected_bundles,
                   f"Collection cards rendered {bundle_cards.count()} navigable cards; expected {expected_bundles}")
            featured_cards = page.locator(".featured-grid .featured-card[data-store-url]")
            record(featured_cards.count() == 6,
                   f"Featured section rendered {featured_cards.count()} navigable cards; expected 6")
            all_product_cards = page.locator(".featured-grid .featured-card[data-store-url], #bundles .bundle[data-store-url], #works .work[data-store-url]")
            for card in all_product_cards.all():
                destination = card.get_attribute("data-store-url") or ""
                record(destination.startswith("https://alshayebemad.gumroad.com/l/"),
                       f"Product card has an invalid Gumroad destination: {destination}")
            for selector in (".featured-grid .featured-card", "#bundles .bundle", "#works .work"):
                card = page.locator(selector).first
                if card.count():
                    destination = card.get_attribute("data-store-url")
                    with context.expect_page() as popup_info:
                        card.locator(".art-mockup").click()
                    popup = popup_info.value
                    popup.wait_for_load_state("domcontentloaded", timeout=10000)
                    record(popup.url == destination,
                           f"Clicking {selector} opened {popup.url}, expected {destination}")
                    popup.close()
            first_artwork = next(x for x in PUBLISHED if not x.get("is_bundle"))
            search = page.locator("#search")
            search.fill(first_artwork["name"])
            record(page.locator("#works .work").count() >= 1, "Artwork title search did not return its matching item")
            search.fill("no-such-artwork-query")
            record(page.locator("#works .work").count() == 0, "Empty search results did not clear the gallery")
            search.fill("")
            category = first_artwork.get("category")
            if category:
                page.locator("#filters button").filter(has_text=category).first.click()
                record(page.locator("#works .work").count() >= 1, "Artwork category filter returned no matching items")
            for product in PUBLISHED:
                path = f"landing/{product['landing_slug']}/index.html"
                inspect_page(page, path, PRODUCT_WIDTHS, expected_product=True)
                buy_links = page.locator(f'a[href="{product["url"]}"]').count()
                record(buy_links >= 1, f"{path}: verified Gumroad purchase link is missing")
            browser.close()
    finally:
        server.shutdown()

    print(f"Responsive audit inspected {PAGE_COUNT} pages across {len(HOME_WIDTHS)} homepage and {len(PRODUCT_WIDTHS)} product viewport widths.")
    print(f"Published catalogue products checked: {len(PUBLISHED)}")
    print(f"Broken or unavailable images: {len(IMAGE_FAILURES)}")
    for item in IMAGE_FAILURES[:100]:
        print("IMAGE:", item)
    print(f"Layout, accessibility and SEO failures: {len(FAILURES)}")
    for item in FAILURES[:100]:
        print("FAIL:", item)
    if FAILURES or IMAGE_FAILURES:
        raise SystemExit(1)
    print("PASS: responsive layout, image loading, alt text, canonical metadata and Product structured data.")

if __name__ == "__main__":
    main()
