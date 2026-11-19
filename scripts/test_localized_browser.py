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
LANGUAGES = json.loads((ROOT / "locales/languages.json").read_text(encoding="utf-8"))
ARABIC_ENTRY = next(item for item in LANGUAGES["languages"] if item["code"] == "ar")
assert ARABIC_ENTRY["available"] is True, "Arabic must be genuinely enabled in locales/languages.json"
PRODUCTS = [p for p in CATALOG["products"] if p.get("published") is True]

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
    page.goto(LOCAL_BASE, wait_until="domcontentloaded")
    page.wait_for_function("document.documentElement.dataset.language === 'en'")
    home_options = page.locator("#language-select").evaluate("(el) => Array.from(el.options).map(option => option.value)")
    assert "ar" in home_options, f"Arabic option missing from test registry: {home_options}"
    wait_language(page, "en", "ltr")
    english_hero = page.locator(".hero h1").inner_text()
    assert "Art, knowledge" in english_hero
    assert page.locator("#art-decor .head h2").inner_text() == "Art & Decor"
    assert page.locator("#ebooks .head h2").inner_text() == "E-Books"
    assert page.locator("#courses .head h2").inner_text() == "Educational Courses"
    section_descriptions = [page.locator(f"#{section} .head p").inner_text() for section in ("art-decor", "ebooks", "courses")]
    assert len(set(section_descriptions)) == 3, "Each storefront section must have its own description"

    page.select_option("#language-select", "ar")
    wait_language(page, "ar", "rtl")
    arabic_hero = normalized(page.locator(".hero h1").inner_text())
    assert "فن يحمل حكاية." in arabic_hero, arabic_hero
    assert page.locator("#art-decor .head h2").inner_text() == "الفن والديكور"
    assert page.locator("#ebooks .head h2").inner_text() == "الكتب الإلكترونية"
    assert page.locator("#courses .head h2").inner_text() == "الكورسات التعليمية"
    assert page.locator("#ebook-search").get_attribute("placeholder") == "ابحث في الكتب الإلكترونية..."
    assert page.locator("#course-search").get_attribute("placeholder") == "ابحث في الكورسات التعليمية..."
    for unit in ("art", "ebooks", "courses"):
        assert page.locator(f'[data-gallery-unit="{unit}"] .section-links a[href="https://alshayebemad.gumroad.com/"]').inner_text() == "تفضل بزيارة متجر Gumroad ↗"
    assert page.locator("#artist").count() == 1
    assert page.locator("footer a[href='./terms.html']").count() == 1
    assert page.evaluate("localStorage.getItem('hog-language')") == "ar"

    page.reload(wait_until="domcontentloaded")
    wait_language(page, "ar", "rtl")
    assert "فن يحمل حكاية." in normalized(page.locator(".hero h1").inner_text())

    page.select_option("#language-select", "en")
    wait_language(page, "en", "ltr")
    assert "Art, knowledge" in page.locator(".hero h1").inner_text()
    assert page.evaluate("localStorage.getItem('hog-language')") == "en"

    page.reload(wait_until="domcontentloaded")
    wait_language(page, "en", "ltr")
    assert "Art, knowledge" in page.locator(".hero h1").inner_text()
    page.close()

def test_all_product_pages(browser):
    page = browser.new_page(locale="en-US")
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
        content_type = product.get("content_type", "art-decor")
        assert page.locator("body").get_attribute("data-content-type") == content_type, f"{slug}: content type marker mismatch"
        if content_type in {"ebook", "course"}:
            assert page.locator("#room-showcase, #printing, .purchase-strip").count() == 0, f"{slug}: art-only display or print copy leaked into {content_type}"
            module = "#reading-experience.ebook-experience" if content_type == "ebook" else "#learning-experience.course-experience"
            assert page.locator(module).count() == 1, f"{slug}: dedicated {content_type} module missing"

        page.select_option("#hog-page-language", "ar")
        wait_language(page, "ar", "rtl")
        expected_title = ARABIC["products"][slug]["title_ar"]
        actual_title = page.locator("[data-hog-title]").inner_text().strip()
        assert actual_title == expected_title, f"{slug}: expected {expected_title!r}, got {actual_title!r}"
        assert page.locator("[data-hog-full-description]").count() == 1
        assert page.locator("[data-hog-full-description]").inner_text().strip()
        if content_type == "ebook":
            assert "كتاب إلكتروني" in page.locator("[data-hog-category]").inner_text(), f"{slug}: Arabic e-book category label missing"
            assert "افتح آفاقاً جديدة" in page.locator(".closing h2").inner_text(), f"{slug}: Arabic e-book call to action missing"
        elif content_type == "course":
            assert "دورة تعليمية" in page.locator("[data-hog-category]").inner_text(), f"{slug}: Arabic course category label missing"
            assert "خطوتك التالية" in page.locator(".closing h2").inner_text(), f"{slug}: Arabic course call to action missing"

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
    options = page.locator("#language-select option").evaluate_all("(nodes) => nodes.map(n => n.value)")
    assert "ar" in options, f"Arabic missing from published homepage selector: {options}"
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
    assert "Art, knowledge" in page.locator(".hero h1").inner_text()
    print("PUBLISHED HOMEPAGE: genuine Arabic option, Arabic ↔ English, RTL/LTR, and refresh persistence passed.")

    tested = 0
    for product in PRODUCTS:
        slug = product["permalink"]
        landing_slug = product["landing_slug"]
        page.goto(LIVE_BASE + "landing/" + landing_slug + "/", wait_until="domcontentloaded", timeout=60000)
        page.locator(f"body[data-product-permalink='{slug}']").wait_for(timeout=30000)
        page.wait_for_function("document.documentElement.lang === 'en'", timeout=20000)
        selector = page.locator("#hog-page-language")
        selector.wait_for(timeout=15000)
        options = selector.evaluate("(el) => Array.from(el.options).map(option => option.value)")
        assert "ar" in options, f"{slug}: Arabic missing from published product selector: {options}"
        english_title = page.locator("[data-hog-title]").inner_text().strip()
        assert english_title, f"{slug}: published English title is empty"
        page.select_option("#hog-page-language", "ar")
        wait_language(page, "ar", "rtl")
        expected_title = ARABIC["products"][slug]["title_ar"]
        actual_title = page.locator("[data-hog-title]").inner_text().strip()
        assert actual_title == expected_title, f"{slug}: expected Arabic title {expected_title!r}, got {actual_title!r}"
        description = page.locator("[data-hog-full-description]").inner_text().strip()
        assert description, f"{slug}: published Arabic description is empty"
        page.select_option("#hog-page-language", "en")
        wait_language(page, "en", "ltr")
        assert page.locator("[data-hog-title]").inner_text().strip() == english_title, f"{slug}: English title did not restore"
        tested += 1
    print(f"PUBLISHED PRODUCT PAGES: {tested}/{len(PRODUCTS)} passed genuine Arabic ↔ English switching, RTL/LTR, title and description checks.")
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
