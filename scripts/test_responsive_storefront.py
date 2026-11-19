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
            page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
            page.set_default_timeout(10000)
            inspect_page(page, "index.html", HOME_WIDTHS, expected_product=False)
            # Five independent units, fixed header/footer, and two-column product grids.
            units = page.locator("[data-gallery-unit]")
            record(units.count() == 4, f"Expected 4 lower-page units (three product units plus artist/footer), found {units.count()}")
            for unit_name in ("art", "ebooks", "courses", "about"):
                record(page.locator(f'[data-gallery-unit="{unit_name}"]').count() == 1,
                       f"Missing or duplicated {unit_name} gallery unit")
            for grid_id in ("art-products", "ebook-products", "course-products"):
                columns = page.locator(f"#{grid_id}").evaluate("(el) => getComputedStyle(el).gridTemplateColumns.split(' ').length")
                record(columns == 2, f"{grid_id}: expected two columns at desktop, found {columns}")
            for unit in page.locator("[data-gallery-unit]").all():
                margin = page.evaluate("(el) => parseFloat(getComputedStyle(el).marginTop)", unit)
                record(margin >= 7.5, f"{unit.get_attribute('data-gallery-unit')}: unit spacing is below 2mm")

            section_specs = [
                ("art-decor", "art-products", "art-decor", "art-load-more-wrap", "art"),
                ("ebooks", "ebook-products", "ebook", "ebook-load-more-wrap", "ebooks"),
                ("courses", "course-products", "course", "course-load-more-wrap", "courses"),
            ]
            for section_id, grid_id, content_type, more_id, unit_id in section_specs:
                expected = [p for p in PUBLISHED if p.get("content_type") == content_type]
                cards = page.locator(f"#{grid_id} .product-card")
                initial = min(4, len(expected))
                record(cards.count() == initial,
                       f"{section_id}: expected {initial} initial product cards, found {cards.count()}")
                previous = initial
                while page.locator(f"#{more_id} button").count():
                    page.locator(f"#{more_id} button").click()
                    current = cards.count()
                    record(current == min(previous + 4, len(expected)),
                           f"{section_id}: Show more should reveal four additional products (or final remainder); found {current}")
                    record(current > previous, f"{section_id}: Show more did not reveal additional products")
                    previous = current
                record(cards.count() == len(expected),
                       f"{section_id}: pagination did not reveal all {len(expected)} products")
                seen = set()
                for product in expected:
                    card = page.locator(f'#{grid_id} .product-card[data-permalink="{product["permalink"]}"]')
                    record(card.count() == 1,
                           f"{section_id}: product {product['permalink']} is missing or duplicated")
                    if card.count() == 1:
                        seen.add(product["permalink"])
                        record(card.get_attribute("data-product-url") == product["url"],
                               f"{section_id}: incorrect Gumroad destination for {product['permalink']}")
                        record(card.locator(f'a[href="{product["url"]}"]').count() == 1,
                               f"{section_id}: exact Gumroad purchase link missing for {product['permalink']}")
                record(len(seen) == len(expected), f"{section_id}: product set is incomplete after pagination")
                record(page.locator(f'[data-gallery-unit="{unit_id}"] .section-links a[href="https://alshayebemad.gumroad.com/"]').count() == 1,
                       f"{section_id}: Gumroad store referral link is missing")

            # No product may leak into a different section after all batches are expanded.
            for product in PUBLISHED:
                expected_grid = {"art-decor": "art-products", "ebook": "ebook-products", "course": "course-products"}[product["content_type"]]
                for _, grid_id, _, _, _ in section_specs:
                    count = page.locator(f'#{grid_id} .product-card[data-permalink="{product["permalink"]}"]').count()
                    record(count == (1 if grid_id == expected_grid else 0),
                           f"{product['permalink']}: duplicated or misclassified across section grids")

            # Preserve the original art search and category filtering behavior.
            first_artwork = next(p for p in PUBLISHED if p.get("content_type") == "art-decor" and not p.get("is_bundle"))
            search = page.locator("#art-search")
            search.fill(first_artwork["name"])
            record(page.locator("#art-products .product-card").count() >= 1,
                   "Art title search did not return its matching product")
            search.fill("no-such-artwork-query")
            record(page.locator("#art-products .product-card").count() == 0,
                   "Empty art search did not clear the art section")
            search.fill("")
            category = first_artwork.get("category")
            if category:
                page.locator("#art-filters button").filter(has_text=category).first.click()
                record(page.locator("#art-products .product-card").count() >= 1,
                       "Art category filter returned no matching item")
                page.locator("#art-filters button").filter(has_text="All").first.click()

            # Verify that clicking the card surface and keyboard activation open
            # the exact Gumroad product, while explicit detail links remain intact.
            first_card = page.locator("#art-products .product-card").first
            expected_url = first_card.get_attribute("data-product-url")
            with page.expect_popup() as popup_info:
                first_card.click(position={"x": 12, "y": 12})
            popup = popup_info.value
            record(popup.url == expected_url, "Card-surface click did not open its exact Gumroad URL")
            popup.close()
            first_card.focus()
            with page.expect_popup() as keyboard_popup_info:
                page.keyboard.press("Enter")
            keyboard_popup = keyboard_popup_info.value
            record(keyboard_popup.url == expected_url, "Keyboard activation did not open the exact Gumroad URL")
            keyboard_popup.close()
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
