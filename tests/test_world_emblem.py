#!/usr/bin/env python3
"""Focused browser QA for the global animated emblem and crown header."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)
    def log_message(self, *_args):
        pass

def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8766), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto("http://127.0.0.1:8766/index.html", wait_until="domcontentloaded")
            page.wait_for_selector(".hog-emblem[data-hog-world-emblem]")
            page.wait_for_function("document.querySelectorAll('.hog-orbit-flag').length === 24")
            page.wait_for_function("document.querySelector('.hog-active-flag.is-center') !== null")
            country_count = page.locator(".hog-active-flag").evaluate(
                "(el) => document.querySelector('.hog-emblem').dataset.ready === 'true' ? true : false"
            )
            script = page.locator("script[src='./assets/world-emblem.js']").get_attribute("src")
            js = page.request.get("http://127.0.0.1:8766/assets/world-emblem.js").text()
            assert "const allCodes=[" in js
            codes = js.split("const allCodes=[", 1)[1].split("];", 1)[0].split(",")
            assert len(codes) >= 240, f"Expected at least 240 ISO flag codes, got {len(codes)}"
            assert page.locator(".hog-crown-tile").count() == 1
            assert page.locator(".hog-crown-tile svg").count() == 1
            assert page.locator(".hog-wordmark").inner_text() == "HALL OF GREATNESS"
            assert page.locator(".hog-header-identity .hog-brand .hog-wordmark").count() == 0
            first = page.locator(".hog-active-flag.is-center").get_attribute("alt")
            page.wait_for_timeout(3200)
            still_first = page.locator(".hog-active-flag.is-center").get_attribute("alt")
            assert still_first == first, f"Flag left center before 3 seconds: {first!r} -> {still_first!r}"
            page.wait_for_function(
                "(first) => { const el=document.querySelector('.hog-active-flag.is-center'); return el && el.alt !== first; }",
                arg=first, timeout=2500,
            )
            second = page.locator(".hog-active-flag.is-center").get_attribute("alt")
            assert first != second
            assert page.locator(".hog-active-flag.is-center").count() == 1
            assert page.locator(".hog-orbit-flag").count() == 24
            assert page.locator(".hog-crown-tile").evaluate("(el)=>getComputedStyle(el).aspectRatio") == "1 / 1"
            for section in ("art-decor", "ebooks", "courses", "artist"):
                assert page.locator(f"#{section}").count() == 1, f"Missing existing section: {section}"
            page.set_viewport_size({"width": 360, "height": 800})
            page.wait_for_timeout(100)
            overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
            assert not overflow, "Header causes horizontal overflow on a 360px phone viewport"
            print(f"PASS: {len(codes)} country/territory flags in rotation; 24 orbit flags; crown tile and separate wordmark; 3-second center hold; no 360px overflow; storefront sections preserved.")
            browser.close()
    finally:
        server.shutdown()

if __name__ == "__main__":
    main()
