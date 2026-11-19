#!/usr/bin/env python3
"""Browser QA for the complete compact header and storefront integrity."""
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
    assert page.locator(".hog-emblem[data-hog-world-emblem]").count() == 1
    assert page.locator(".hog-crown-tile").count() == 1
    assert page.locator(".hog-wordmark").inner_text() == "HALL OF GREATNESS"
    assert language.count() == 1
    assert nav.locator("a").count() == 4
    for section in ("art-decor", "ebooks", "courses", "artist"):
        assert page.locator(f"#{section}").count() == 1, f"Missing storefront section: {section}"
    assert page.locator("#art-tools #art-search").count() == 1, "Artwork search must remain in its original section"
    assert page.locator("#art-tools #art-filters").count() == 1, "Artwork filters must remain in their original section"
    assert header.evaluate("(el)=>getComputedStyle(el).position") == "sticky"
    assert language.is_visible(), "Language selector must be visible in the full header"
    assert all(link.is_visible() for link in nav.locator("a").all()), "All section links must be visible in the full header"

    original_hero_document_y = page.evaluate("() => document.querySelector('main .hero').getBoundingClientRect().top + window.scrollY")
    page.evaluate("window.scrollTo(0, 500)")
    page.wait_for_function("document.querySelector('.wrap>header').dataset.compact === 'true'")
    page.wait_for_function("""() => {
      const h=document.querySelector('.wrap>header');
      const l=document.querySelector('#language-select');
      const n=document.querySelector('header nav');
      return h.classList.contains('is-compact') && l.getBoundingClientRect().width >= 90 &&
        l.getBoundingClientRect().height >= 28 && getComputedStyle(l).visibility === 'visible' &&
        [...n.querySelectorAll('a')].every(a => {
          const r=a.getBoundingClientRect(),s=getComputedStyle(a);
          return r.width >= 24 && r.height >= 24 && s.visibility === 'visible' && s.opacity !== '0';
        });
    }""", timeout=5000)
    page.wait_for_timeout(450)
    box = header.bounding_box()
    compact_hero_document_y = page.evaluate("() => document.querySelector('main .hero').getBoundingClientRect().top + window.scrollY")
    assert abs(compact_hero_document_y - original_hero_document_y) <= 2, f"Header transition shifted page content by {compact_hero_document_y - original_hero_document_y:.2f}px"
    assert box and box["y"] <= 1, f"Sticky header moved off screen: {box}"
    assert page.locator(".hog-emblem").is_visible()
    assert page.locator(".hog-crown-tile").is_visible()
    assert page.locator(".hog-wordmark").is_visible()
    assert language.is_visible(), "Language selector disappeared in compact mode"
    assert all(link.is_visible() for link in nav.locator("a").all()), "A section link disappeared in compact mode"
    assert box["height"] <= 115, f"Complete compact header is too tall: {box['height']}px"
    assert page.locator("#art-tools #art-search").count() == 1, "Search was moved or duplicated"
    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    assert not overflow, f"Horizontal overflow at viewport width {width}"

    # Return to the top and verify the full header restores without losing controls.
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_function("""() => {
      const h=document.querySelector('.wrap>header');
      return window.scrollY <= 1 && h.dataset.compact === 'false' && !h.classList.contains('is-compact');
    }""", timeout=5000)
    page.wait_for_timeout(450)
    assert language.is_visible(), "Language selector did not restore at page top"
    assert all(link.is_visible() for link in nav.locator("a").all()), "Navigation did not restore at page top"
    page.close()

def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8766), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for width, height in ((390, 844), (360, 800), (768, 1024), (1280, 900)):
                check_viewport(browser, width, height)
            print("PASS: compact header retains emblem, crown, wordmark, language selector and all four navigation links; search and filters remain in Art & Decor; full header restores at top; no horizontal overflow at 390, 360, 768 or 1280px.")
            browser.close()
    finally:
        server.shutdown()

if __name__ == "__main__":
    main()
