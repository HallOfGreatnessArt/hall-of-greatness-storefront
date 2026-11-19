#!/usr/bin/env python3
"""Browser QA for the permanent compact header and storefront integrity."""
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
    language = page.locator("#language-select")
    nav = page.locator("header nav")
    assert header.count() == 1
    assert header.evaluate("(el)=>el.dataset.layout") == "fixed-compact"
    assert header.evaluate("(el)=>!el.classList.contains('is-compact')")
    assert header.evaluate("(el)=>getComputedStyle(el).position") == "sticky"
    assert page.locator(".hog-emblem[data-hog-world-emblem]").count() == 1
    assert page.locator(".hog-crown-tile").count() == 1
    assert page.locator(".hog-wordmark").inner_text() == "HALL OF GREATNESS"
    assert language.is_visible()
    assert nav.locator("a").count() == 4
    assert all(link.is_visible() for link in nav.locator("a").all())
    assert page.locator("#art-tools #art-search").count() == 1
    assert page.locator("#art-tools #art-filters").count() == 1
    for section in ("art-decor", "ebooks", "courses", "artist"):
        assert page.locator(f"#{section}").count() == 1

    initial_height = header.evaluate("(el)=>el.getBoundingClientRect().height")
    initial_document_y = page.evaluate("() => document.querySelector('main .hero').getBoundingClientRect().top + window.scrollY")
    for scroll_y in (80, 500, 1100, 0, 700, 0):
        page.evaluate("(y)=>window.scrollTo(0,y)", scroll_y)
        page.wait_for_timeout(100)
        current_height = header.evaluate("(el)=>el.getBoundingClientRect().height")
        current_document_y = page.evaluate("() => document.querySelector('main .hero').getBoundingClientRect().top + window.scrollY")
        assert abs(current_height - initial_height) <= 0.5, f"Header height changed while scrolling: {initial_height} -> {current_height}"
        assert abs(current_document_y - initial_document_y) <= 1, f"Page content jumped while scrolling: {initial_document_y} -> {current_document_y}"
        assert language.is_visible(), "Language selector disappeared while scrolling"
        assert all(link.is_visible() for link in nav.locator("a").all()), "Navigation link disappeared while scrolling"
    box = header.bounding_box()
    assert box and box["height"] <= (120 if width <= 900 else 76), f"Fixed header takes too much space: {box}"
    emblem_box = page.locator(".hog-emblem").bounding_box()
    identity_box = page.locator(".hog-header-identity").bounding_box()
    assert emblem_box and identity_box
    assert emblem_box["height"] >= (60 if width <= 900 else 38), f"Emblem is too small: {emblem_box}"
    assert emblem_box["y"] >= identity_box["y"] - 1 and emblem_box["y"] + emblem_box["height"] <= identity_box["y"] + identity_box["height"] + 1, f"Emblem orbit is clipped by identity row: emblem={emblem_box}, identity={identity_box}"
    orbit_flags = page.locator(".hog-orbit-flag")
    page.wait_for_function("document.querySelectorAll('.hog-orbit-flag').length === 24")
    assert orbit_flags.count() == 24
    assert page.locator(".hog-emblem").is_visible()
    assert page.locator(".hog-crown-tile").is_visible()
    assert page.locator(".hog-wordmark").is_visible()
    assert not page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"), f"Horizontal overflow at {width}px"
    page.close()

def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8766), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for width, height in ((390, 844), (360, 800), (768, 1024), (1280, 900)):
                check_viewport(browser, width, height)
            print("PASS: permanent compact header has identical height at every scroll position; identity, language and all four links stay visible; artwork search and filters remain in place; no horizontal overflow.")
            browser.close()
    finally:
        server.shutdown()

if __name__ == "__main__":
    main()
