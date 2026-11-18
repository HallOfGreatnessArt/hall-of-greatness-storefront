#!/usr/bin/env python3
"""Focused browser QA for the isolated animated world emblem."""
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
            first = page.locator(".hog-active-flag.is-center").get_attribute("alt")
            # The first flag must remain centered for the full three seconds,
            # even after its entrance animation has completed.
            page.wait_for_timeout(3200)
            still_first = page.locator(".hog-active-flag.is-center").get_attribute("alt")
            assert still_first == first, f"Flag left the center before 3 seconds: {first!r} -> {still_first!r}"
            # The previous flag returns before the next flag takes the center.
            page.wait_for_function(
                "(first) => { const el=document.querySelector('.hog-active-flag.is-center'); return el && el.alt !== first; }",
                arg=first,
                timeout=2500,
            )
            second = page.locator(".hog-active-flag.is-center").get_attribute("alt")
            assert first != second, f"Sequential flag did not advance: {first!r}"
            assert page.locator(".hog-active-flag.is-center").count() == 1
            assert page.locator(".hog-orbit-flag").count() == 24
            assert page.locator(".hog-brand .hog-wordmark").inner_text() == "HALL OF GREATNESS"
            transform = page.locator(".hog-emblem").evaluate("(el) => getComputedStyle(el).transform")
            assert transform in ("none", "matrix(1, 0, 0, 1, 0, 0)"), f"Gold emblem moved: {transform}"
            for section in ("art-decor", "ebooks", "courses", "artist"):
                assert page.locator(f"#{section}").count() == 1, f"Missing existing section: {section}"
            print(f"PASS: 24 orbit flags; each flag holds center for 3 seconds; sequence advances {first} -> {second}; fixed emblem; existing sections present.")
            browser.close()
    finally:
        server.shutdown()

if __name__ == "__main__":
    main()
