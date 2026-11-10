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
    page.wait_for_timeout(900)
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
    for image in metadata["images"]:
        record(bool(image["alt"]), f"{path}: image missing alt text: {image['src']}")
        if not image["loaded"]:
            IMAGE_FAILURES.append(f"{path}: image failed to load: {image['src']}")

    if expected_product:
        schema = page.locator('script#product-jsonld').count()
        record(schema == 1, f"{path}: expected exactly one Product JSON-LD block")

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
            home_cards = page.locator("#works .work").count()
            record(home_cards >= len([x for x in PUBLISHED if not x.get("is_bundle")]),
                   f"Homepage gallery did not render the expected artwork cards ({home_cards})")
            for product in PUBLISHED:
                path = f"landing/{product['landing_slug']}/index.html"
                inspect_page(page, path, PRODUCT_WIDTHS, expected_product=True)
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
