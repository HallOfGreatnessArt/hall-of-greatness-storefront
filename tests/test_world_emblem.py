#!/usr/bin/env python3
"""Mobile and desktop browser QA for sticky gallery identity and storefront integrity."""
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

def check_viewport(browser, width, height):
    page = browser.new_page(viewport={"width": width, "height": height})
    page.goto("http://127.0.0.1:8766/index.html", wait_until="domcontentloaded")
    header = page.locator(".wrap>header")
    assert header.count() == 1
    assert page.locator(".hog-emblem[data-hog-world-emblem]").count() == 1
    assert page.locator(".hog-crown-tile").count() == 1
    assert page.locator(".hog-wordmark").inner_text() == "HALL OF GREATNESS"
    assert page.locator("#language-select").count() == 1
    for section in ("art-decor", "ebooks", "courses", "artist"):
        assert page.locator(f"#{section}").count() == 1, f"Missing storefront section: {section}"
    position = header.evaluate("(el)=>getComputedStyle(el).position")
    assert position == "sticky", f"Header must be sticky, got {position}"
    page.evaluate("window.scrollTo(0, 500)")
    page.wait_for_function("document.querySelector('.wrap>header').dataset.compact === 'true'")
    box = header.bounding_box()
    assert box["y"] <= 1, f"Sticky header moved off screen: y={box['y']}"
    assert page.locator(".hog-emblem").is_visible()
    assert page.locator(".hog-crown-tile").is_visible()
    assert page.locator(".hog-wordmark").is_visible()
    assert page.locator("#language-select").is_hidden()
    assert page.locator("header nav").is_hidden()
    compact_height = box["height"]
    assert compact_height <= 100, f"Compact header too tall: {compact_height}px"
    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    assert not overflow, f"Horizontal overflow at viewport width {width}"
    page.evaluate("""() => {
        window.scrollTo({top: 0, behavior: 'instant'});
        window.dispatchEvent(new Event('scroll'));
    }""")
    page.wait_for_function("""() => {
        const header = document.querySelector('.wrap>header');
        return window.scrollY === 0 &&
               header.dataset.compact === 'false' &&
               !header.classList.contains('is-compact');
    }""", timeout=3000)
    page.wait_for_function("""() => {
        const language = document.querySelector('#language-select');
        const nav = document.querySelector('header nav');
        return !!language && !!nav &&
               getComputedStyle(language).display !== 'none' &&
               getComputedStyle(nav).display !== 'none';
    }""", timeout=3000)
    assert page.locator("#language-select").is_visible()
    assert page.locator("header nav").is_visible()
    page.close()

def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8766), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for width, height in ((390, 844), (360, 800), (768, 1024), (1280, 900)):
                check_viewport(browser, width, height)
            print("PASS: sticky compact identity remains visible while scrolling; emblem, crown and wordmark persist; full header restores at top; language/navigation remain available at top; all four storefront sections preserved; no horizontal overflow at 390, 360, 768 or 1280px.")
            browser.close()
    finally:
        server.shutdown()

if __name__ == "__main__":
    main()
