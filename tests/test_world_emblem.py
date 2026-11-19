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
    # Return to the top using the browser's normal scroll path, then wait for
    # the real scroll event and the compact-state update (avoid synthetic timing races).
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_function("window.scrollY <= 1", timeout=5000)
    page.wait_for_function("""() => {
        const header = document.querySelector('.wrap>header');
        return header.dataset.compact === 'false' &&
               !header.classList.contains('is-compact');
    }""", timeout=5000)
    # Assert the real mobile control is rendered, has a usable hit area,
    # and is not covered/hidden after the full header is restored.
    page.wait_for_function("""() => {
        const select = document.querySelector('#language-select');
        const tools = document.querySelector('header .header-tools');
        const nav = document.querySelector('header nav');
        if (!select || !tools || !nav) return false;
        const r = select.getBoundingClientRect();
        const s = getComputedStyle(select);
        const p = getComputedStyle(tools);
        return s.display !== 'none' && s.visibility === 'visible' &&
               p.display !== 'none' && p.visibility === 'visible' &&
               r.width >= 100 && r.height >= 32 &&
               getComputedStyle(nav).display !== 'none';
    }""", timeout=5000)
    select = page.locator("#language-select")
    assert select.is_visible(), "Language selector is not visibly rendered after returning to page top"
    assert select.locator("option").count() >= 2, "Language selector has no usable choices"
    # Read rendered geometry in-page to avoid a transient Playwright
    # bounding_box None during native select/layout updates.
    geometry = page.evaluate("""() => {
        const el = document.querySelector('#language-select');
        if (!el) return null;
        const r = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return {
            x: r.x, y: r.y, width: r.width, height: r.height,
            display: style.display, visibility: style.visibility,
            opacity: Number(style.opacity)
        };
    }""")
    assert geometry, "Language selector has no rendered geometry"
    assert geometry["display"] != "none" and geometry["visibility"] == "visible" and geometry["opacity"] > 0, f"Language selector is visually hidden: {geometry}"
    assert geometry["width"] >= 100 and geometry["height"] >= 32, f"Language selector has no usable touch target: {geometry}"
    hit = page.evaluate("""() => {
        const el = document.querySelector('#language-select');
        const r = el.getBoundingClientRect();
        const x = r.left + r.width / 2;
        const y = r.top + r.height / 2;
        const top = document.elementFromPoint(x, y);
        return {hit: !!top && (top === el || el.contains(top)), x, y,
                viewport: {width: innerWidth, height: innerHeight}};
    }""")
    assert hit["hit"], f"Language selector is covered and cannot receive a tap: {hit}"
    # Verify the actual navigation controls, not only the nav wrapper's
    # visibility (the wrapper may report a zero-area box during flex reflow).
    nav = page.locator("header nav")
    assert nav.count() == 1
    assert nav.locator("a").count() == 4
    for link in nav.locator("a").all():
        assert link.is_visible(), f"Navigation link is not visible: {link.inner_text()}"
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
