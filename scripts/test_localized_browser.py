#!/usr/bin/env python3
"""Real Chromium checks for the local PR build and the published GitHub Pages site."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
LOCAL_BASE = "http://127.0.0.1:8000/"
LIVE_BASE = "https://hallofgreatnessart.github.io/hall-of-greatness-storefront/"
CATALOG = json.loads((ROOT / "catalog-data.json").read_text(encoding="utf-8"))
ARABIC = json.loads((ROOT / "locales/ar.json").read_text(encoding="utf-8"))
PRODUCTS = [p for p in CATALOG["products"] if p.get("published") is True]

PATCH_AR_AVAILABLE = r"""
(() => {
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await originalFetch(...args);
    const input = args[0];
    const url = new URL(typeof input === "string" ? input : input.url, window.location.href);
    if (url.pathname.endsWith("/locales/languages.json")) {
      const registry = await response.clone().json();
      const arabic = (registry.languages || []).find(item => item.code === "ar");
      if (arabic) arabic.available = true;
      return new Response(JSON.stringify(registry), {
        status: response.status,
        headers: {"Content-Type": "application/json"}
      });
    }
    return response;
  };
})();
"""

def wait_language(page, code: str, direction: str):
    page.wait_for_function(
        """([lang, dir]) =>
          document.documentElement.lang === lang &&
          document.documentElement.dir === dir""",
        arg=[code, direction],
        timeout=15000,
    )

def normalized(text: str) -> str:
    return " ".join(text.split())

def test_local_homepage(browser):
    page = browser.new_page(locale="en-US")
    page.add_init_script(PATCH_AR_AVAILABLE)
    page.goto(LOCAL_BASE, wait_until="domcontentloaded")
    page.wait_for_function("document.documentElement.dataset.language === 'en'")
    home_options = page.locator("#language-select").evaluate("(el) => Array.from(el.options).map(option => option.value)")
    assert "ar" in home_options, f"Arabic option missing from test registry: {home_options}"
    wait_language(page, "en", "ltr")
    english_hero = page.locator(".hero h1").inner_text()
    assert "Art that carries" in english_hero

    page.select_option("#language-select", "ar")
    wait_language(page, "ar", "rtl")
    arabic_hero = normalized(page.locator(".hero h1").inner_text())
    assert "فن يحمل حكاية." in arabic_hero, arabic_hero
    assert page.evaluate("localStorage.getItem('hog-language')") == "ar"

    page.reload(wait_until="domcontentloaded")
    wait_language(page, "ar", "rtl")
    assert "فن يحمل حكاية." in normalized(page.locator(".hero h1").inner_text())

    page.select_option("#language-select", "en")
    wait_language(page, "en", "ltr")
    assert "Art that carries" in page.locator(".hero h1").inner_text()
    assert page.evaluate("localStorage.getItem('hog-language')") == "en"

    page.reload(wait_until="domcontentloaded")
    wait_language(page, "en", "ltr")
    assert "Art that carries" in page.locator(".hero h1").inner_text()
    page.close()

def test_all_product_pages(browser):
    page = browser.new_page(locale="en-US")
    page.add_init_script(PATCH_AR_AVAILABLE)
    tested = 0
    for product in PRODUCTS:
        slug = product["permalink"]
        landing_slug = product["landing_slug"]
        page.goto(LOCAL_BASE + "landing/" + landing_slug + "/", wait_until="domcontentloaded")
        selector = page.locator("#hog-page-language")
        selector.wait_for()
        page.wait_for_function("document.querySelector('#hog-page-language').options.length > 1")
        product_options = page.locator("#hog-page-language").evaluate("(el) => Array.from(el.options).map(option => option.value)")
        assert "ar" in product_options, f"{slug}: Arabic option missing from test registry: {product_options}"
        wait_language(page, "en", "ltr")
        original_title = page.locator("[data-hog-title]").inner_text().strip()
        assert original_title, f"{slug}: empty English product title"

        page.select_option("#hog-page-language", "ar")
        wait_language(page, "ar", "rtl")
        expected_title = ARABIC["products"][slug]["title_ar"]
        actual_title = page.locator("[data-hog-title]").inner_text().strip()
        assert actual_title == expected_title, f"{slug}: expected {expected_title!r}, got {actual_title!r}"
        assert page.locator("[data-hog-full-description]").count() == 1
        assert page.locator("[data-hog-full-description]").inner_text().strip()

        page.select_option("#hog-page-language", "en")
        wait_language(page, "en", "ltr")
        restored_title = page.locator("[data-hog-title]").inner_text().strip()
        assert restored_title == original_title, f"{slug}: English title did not restore"
        tested += 1

        if slug == "csyqhm":
            page.select_option("#hog-page-language", "ar")
            wait_language(page, "ar", "rtl")
            page.reload(wait_until="domcontentloaded")
            wait_language(page, "ar", "rtl")
            assert page.locator("[data-hog-title]").inner_text().strip() == expected_title
            page.select_option("#hog-page-language", "en")
            wait_language(page, "en", "ltr")
            page.reload(wait_until="domcontentloaded")
            wait_language(page, "en", "ltr")
            assert page.locator("[data-hog-title]").inner_text().strip() == original_title

    page.close()
    return tested

def test_published_site(browser):
    page = browser.new_page(locale="en-US")
    page.goto(LIVE_BASE, wait_until="domcontentloaded", timeout=60000)
    page.locator("#language-select").wait_for(timeout=30000)
    page.wait_for_function("document.documentElement.lang === 'en'", timeout=20000)
    assert page.locator(".hero h1").inner_text().strip()
    options = page.locator("#language-select option").evaluate_all("(nodes) => nodes.map(n => n.value)")
    print("PUBLISHED HOMEPAGE: loaded in Chromium; available language options:", options)
    if "ar" in options:
        page.select_option("#language-select", "ar")
        wait_language(page, "ar", "rtl")
        assert "فن يحمل حكاية." in normalized(page.locator(".hero h1").inner_text())
        page.reload(wait_until="domcontentloaded")
        wait_language(page, "ar", "rtl")
        assert "فن يحمل حكاية." in normalized(page.locator(".hero h1").inner_text())
        page.select_option("#language-select", "en")
        wait_language(page, "en", "ltr")
        page.reload(wait_until="domcontentloaded")
        wait_language(page, "en", "ltr")
        print("PUBLISHED HOMEPAGE SWITCH: Arabic ↔ English, RTL/LTR, and refresh persistence passed.")
    else:
        print("PUBLISHED HOMEPAGE SWITCH: Arabic is not present in the live selector.")

    page.goto(LIVE_BASE + "landing/the-coptic-soul-of-egypt/", wait_until="domcontentloaded", timeout=60000)
    page.locator("body[data-product-permalink='csyqhm']").wait_for(timeout=30000)
    page.wait_for_function("document.documentElement.lang === 'en'", timeout=20000)
    assert page.locator("h1").first.inner_text().strip()
    print("PUBLISHED PRODUCT PAGE: direct URL loaded in Chromium; default English layout verified.")
    product_select = page.locator("#hog-page-language")
    if product_select.count() and "ar" in product_select.evaluate("(el) => Array.from(el.options).map(option => option.value)"):
        page.select_option("#hog-page-language", "ar")
        wait_language(page, "ar", "rtl")
        assert re.search(r"[\\u0600-\\u06FF]", page.locator("body").inner_text())
        page.reload(wait_until="domcontentloaded")
        wait_language(page, "ar", "rtl")
        page.select_option("#hog-page-language", "en")
        wait_language(page, "en", "ltr")
        page.reload(wait_until="domcontentloaded")
        wait_language(page, "en", "ltr")
        print("PUBLISHED PRODUCT SWITCH: Arabic ↔ English, RTL/LTR, and refresh persistence passed.")
    else:
        print("PUBLISHED PRODUCT SWITCH: Arabic option unavailable on the live product page.")
    page.close()

def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        if "--live-only" not in sys.argv[1:]:
            test_local_homepage(browser)
            count = test_all_product_pages(browser)
            print(f"LOCAL CHROMIUM QA: homepage language switch/return/refresh passed; {count}/{len(PRODUCTS)} product pages switched Arabic ↔ English with RTL/LTR checks.")
        if "--local-only" not in sys.argv[1:]:
            test_published_site(browser)
        browser.close()

if __name__ == "__main__":
    try:
        main()
    except (AssertionError, PlaywrightTimeoutError) as exc:
        print(f"BROWSER QA FAILED: {exc}", file=sys.stderr)
        raise
