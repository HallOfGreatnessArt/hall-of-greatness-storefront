#!/usr/bin/env python3
"""Dedicated local Chromium QA for the six bilingual Gumroad ebook landing previews."""
from __future__ import annotations

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000/gumroad-ebook-landings"
CATALOG = json.loads((ROOT / "catalog-data.json").read_text(encoding="utf-8"))
COPY = json.loads((ROOT / "ebook-copy.json").read_text(encoding="utf-8"))
LANGUAGES = json.loads((ROOT / "locales/languages.json").read_text(encoding="utf-8"))
PRODUCTS = {p["permalink"]: p for p in CATALOG["products"] if p.get("permalink") in COPY}
EVIDENCE = ROOT / "ebook-landing-refresh-evidence" / "screenshots"
EVIDENCE.mkdir(parents=True, exist_ok=True)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    check(len(PRODUCTS) == 6, f"Expected exactly six ebook products; found {len(PRODUCTS)}")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for key, product in PRODUCTS.items():
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            url = f"{BASE}/{key}/landing.html"
            page.goto(url, wait_until="domcontentloaded")
            page.locator("#title").wait_for()
            english = COPY[key]["en"]
            arabic = COPY[key]["ar"]

            check(page.locator("#title").inner_text() == english["title"], f"{key}: English title mismatch")
            check(page.title() == english["title"] + " | HALL OF GREATNESS Publishing", f"{key}: document title metadata mismatch")
            check(bool(page.locator('meta[name="description"]').get_attribute("content")), f"{key}: SEO description metadata missing")
            check(page.locator("html").get_attribute("lang") == "en", f"{key}: initial language is not English")
            check(page.locator("html").get_attribute("dir") == "ltr", f"{key}: English direction is not LTR")
            check(page.locator("#buy").get_attribute("href") == product["url"], f"{key}: primary CTA URL mismatch")
            check(page.locator("#buyBottom").get_attribute("href") == product["url"], f"{key}: closing CTA URL mismatch")
            expected_price = f"${product['price_usd']:.2f} USD"
            check(page.locator("#price").inner_text() == expected_price, f"{key}: price mismatch")
            check(page.locator("#priceBottom").inner_text() == expected_price, f"{key}: repeated price mismatch")
            check(page.locator("#cover").get_attribute("src") == product["cover_url"], f"{key}: cover URL mismatch")
            check(bool(page.locator("#cover").get_attribute("alt")), f"{key}: cover alt text missing")
            check(page.locator("#explore li").count() > 0, f"{key}: subjects section is empty")
            check(page.locator("#takeaways li").count() > 0, f"{key}: reader value section is empty")
            check(bool(page.locator("#audience").inner_text().strip()), f"{key}: audience section is empty")
            check(bool(page.locator("#edition .meta").count()) if page.locator("#edition").count() else page.locator("#meta .meta").count() == 6, f"{key}: edition metadata missing")

            package_visible = page.locator("#packageSection").evaluate("(el) => !el.hidden")
            check(package_visible == bool(english["package"]), f"{key}: package visibility does not match documented files")
            collection_visible = page.locator("#collectionSection").evaluate("(el) => !el.hidden")
            check(collection_visible == (key == "wydjxz"), f"{key}: collection section visibility mismatch")
            bundle = next(p for p in CATALOG["products"] if p.get("permalink") == "wydjxz")
            included = list(bundle["bundle_contents"])
            if key in included:
                included.remove(key)
            expected_urls = sorted(PRODUCTS[item]["url"] for item in included)
            actual_urls = sorted(page.locator("#bookLinks a").evaluate_all("(nodes) => nodes.map(a => a.href)"))
            check(actual_urls == expected_urls, f"{key}: related-book links do not match the verified five-book bundle")

            locale_options = page.locator("#lang").evaluate("(el) => Array.from(el.options).map(option => option.value)")
            check("ar" in locale_options, f"{key}: Arabic missing from validated e-book language options: {locale_options}")
            for code in [value for value in locale_options if value not in ("auto", "en")]:
                page.select_option("#lang", code)
                rtl_entry = next((item for item in LANGUAGES["languages"] if item["code"] == code), {"rtl": False})
                direction = "rtl" if rtl_entry.get("rtl") else "ltr"
                page.wait_for_function("(args) => document.documentElement.lang === args[0] && document.documentElement.dir === args[1]", arg=[code, direction])
                if code == "ar":
                    translated = arabic
                    locale_data = json.loads((ROOT / "locales" / "ar.json").read_text(encoding="utf-8"))
                else:
                    locale_data = json.loads((ROOT / "locales" / f"{code}.json").read_text(encoding="utf-8"))
                    translated = locale_data["ebooks"][key]
                actual_title = page.locator("#title").text_content()
                check(actual_title == translated["title"], f"{key}/{code}: translated title mismatch")
                check(page.title() == translated["title"] + " | HALL OF GREATNESS Publishing", f"{key}/{code}: document title metadata mismatch")
                expected_buy = locale_data["ui"]["landingBuy"]
                check(page.locator("#buy").inner_text() == expected_buy, f"{key}/{code}: localized CTA mismatch")
                check(bool(page.locator("#overview").inner_text().strip()), f"{key}/{code}: translated overview missing")
                check(page.locator("#meta .meta").count() == 6, f"{key}/{code}: metadata incomplete")

            page.select_option("#lang", "ar")
            page.wait_for_function("document.documentElement.lang === 'ar' && document.documentElement.dir === 'rtl'")
            actual_arabic_title = page.locator("#title").text_content()
            check(actual_arabic_title == arabic["title"], f"{key}: Arabic title mismatch; expected={arabic['title']!r}, actual={actual_arabic_title!r}")
            check(page.title() == arabic["title"] + " | HALL OF GREATNESS Publishing", f"{key}: Arabic document title metadata mismatch")
            check(page.locator("#meta .meta").count() == 6, f"{key}: Arabic metadata incomplete")

            # Capture actual Arabic RTL rendering at desktop and mobile sizes.
            page.wait_for_function("document.fonts.status === 'loaded'", timeout=10000)
            page.screenshot(path=str(EVIDENCE / f"{key}-arabic-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(150)
            arabic_overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
            check(not arabic_overflow, f"{key}: Arabic horizontal overflow at 390px")
            page.screenshot(path=str(EVIDENCE / f"{key}-arabic-mobile.png"), full_page=True)
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.wait_for_timeout(100)

            page.select_option("#lang", "en")
            page.wait_for_function("document.documentElement.lang === 'en' && document.documentElement.dir === 'ltr'")
            check(page.locator("#title").inner_text() == english["title"], f"{key}: English title did not restore")

            page.wait_for_function("document.fonts.status === 'loaded'", timeout=10000)
            page.screenshot(path=str(EVIDENCE / f"{key}-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(150)
            overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
            check(not overflow, f"{key}: horizontal overflow at 390px")
            page.screenshot(path=str(EVIDENCE / f"{key}-mobile.png"), full_page=True)
            check(not errors, f"{key}: browser console/page errors: {errors}")
            print(f"PASS {key}: bilingual, RTL/LTR, content, package, links, CTA, price, desktop/mobile")
            page.close()
        browser.close()
    print(f"PASS all {len(PRODUCTS)} ebook pages; screenshots saved to {EVIDENCE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
