#!/usr/bin/env python3
"""Browser-smoke-test real Spanish and Arabic product-page localization."""
from __future__ import annotations

import json
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from translate_landing_pages import extract_page_copy


def main():
    catalog = json.loads((ROOT / "catalog-data.json").read_text(encoding="utf-8"))
    products = {item["landing_slug"]: item for item in catalog["products"] if item.get("published")}
    titles = [str(item.get("name", "")).strip() for item in catalog["products"]]
    titles.append("HALL OF GREATNESS")

    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)

            for language, expected_direction in (("es", "ltr"), ("ar", "rtl")):
                context = browser.new_context()
                page = context.new_page()
                product = products["the-tree-that-refused-to-die"]
                page_path = ROOT / "landing" / product["landing_slug"] / "index.html"
                page_html = page_path.read_text(encoding="utf-8")
                source_texts = extract_page_copy(page_html, titles)

                page.add_init_script(
                    f"localStorage.setItem('hog-language', {json.dumps(language)});"
                )
                page.goto(
                    f"{base}/landing/{product['landing_slug']}/",
                    wait_until="domcontentloaded",
                )
                page.wait_for_function(
                    """([lang, direction]) =>
                      document.documentElement.lang === lang &&
                      document.documentElement.dir === direction &&
                      document.querySelector('#hog-page-language')?.value === lang""",
                    arg=[language, expected_direction],
                    timeout=30000,
                )
                page.wait_for_timeout(300)
                body_text = page.locator("body").inner_text()

                assert "HALL OF GREATNESS" in body_text, f"{language}: brand was changed"
                assert product["name"].strip() in body_text, f"{language}: artwork title was changed"
                assert "Humanity" not in body_text, f"{language}: artwork category remained English"
                for english_heading in ("The meaning behind the artwork", "Digital download details", "Before you purchase", "From download to display"):
                    assert english_heading not in body_text, f"{language}: shared heading remained English: {english_heading}"
                assert "Files included" not in body_text, f"{language}: product-detail label remained English"
                assert "Product type" not in body_text, f"{language}: product type label remained English"
                assert "No physical print or frame will be shipped" not in body_text, f"{language}: buyer detail remained English"
                assert "The Tree That Refused to Die tells a story of resilience" not in body_text, f"{language}: summary remained English"
                assert "What if the greatest symbol of hope was not a monument built by humanity" not in body_text, f"{language}: full artwork narrative remained English"
                for source_text in source_texts:
                    assert source_text not in body_text, (
                        f"{language}: visible page narrative remained in English: {source_text[:100]}"
                    )
                print(
                    f"Browser localization passed: {language}, dir={expected_direction}, "
                    f"{len(source_texts)} artwork-specific source strings checked."
                )
                context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
