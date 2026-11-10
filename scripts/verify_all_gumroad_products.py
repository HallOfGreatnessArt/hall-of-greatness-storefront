#!/usr/bin/env python3
"""Check every catalogue Gumroad URL and create a transparent public-page report.

A successful HTTP response is evidence that a public page loaded, not proof that
Gumroad Discover has approved the product or that checkout is functioning.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

CATALOG = Path("catalog-data.json")
OUT = Path("gumroad-product-verification-report.json")


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    products = [p for p in catalog.get("products", []) if p.get("published")]
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
        )
        page = context.new_page()
        for product in products:
            url = str(product.get("url") or "")
            item = {
                "name": product.get("name"),
                "permalink": product.get("permalink"),
                "catalog_url": url,
                "http_status": None,
                "final_url": None,
                "page_title": None,
                "classification": "unresolved",
                "evidence": [],
            }
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                item["http_status"] = response.status if response else None
                item["final_url"] = page.url
                item["page_title"] = (page.title() or "")[:240]
                body = re.sub(r"\s+", " ", (page.locator("body").inner_text(timeout=10000) or "")).strip()
                low = body.lower()
                title_match = str(product.get("name") or "").strip().lower() in low
                permalink_match = str(product.get("permalink") or "").lower() in page.url.lower()
                unavailable_markers = (
                    "this product is not available", "product not found",
                    "this page does not exist", "has been removed",
                    "is no longer available",
                )
                challenge_markers = (
                    "verify you are human", "security check", "captcha",
                    "checking your browser", "access denied",
                )
                if any(marker in low for marker in challenge_markers):
                    item["classification"] = "blocked_or_challenged"
                    item["evidence"].append("The response appears to be a bot/security challenge; visibility is not confirmed.")
                elif any(marker in low for marker in unavailable_markers) or item["http_status"] == 404:
                    item["classification"] = "not_found_or_unavailable"
                    item["evidence"].append("The page returned an unavailable/not-found signal.")
                elif item["http_status"] == 200 and (title_match or permalink_match):
                    item["classification"] = "public_page_loaded"
                    item["evidence"].append("HTTP 200 and product identity evidence found on the returned page.")
                elif item["http_status"] == 200:
                    item["classification"] = "loaded_identity_unconfirmed"
                    item["evidence"].append("HTTP 200, but product identity could not be confirmed automatically.")
                else:
                    item["classification"] = "http_error_or_unresolved"
                    item["evidence"].append("No definitive public-page confirmation; inspect the status and final URL.")
            except Exception as exc:
                item["classification"] = "request_failed"
                item["evidence"].append(str(exc)[:400])
            results.append(item)
            print(f"{item['classification']}: {product.get('permalink')} | HTTP {item['http_status']}")
        context.close()
        browser.close()

    counts = {}
    for item in results:
        counts[item["classification"]] = counts.get(item["classification"], 0) + 1
    report = {
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": "public unauthenticated Gumroad product-page requests",
        "catalogue_products": len(products),
        "checked_products": len(results),
        "classification_counts": counts,
        "important_limit": (
            "This report checks public page loading and product identity only. "
            "It does not verify checkout, file delivery, account publication settings, "
            "or Gumroad Discover eligibility."
        ),
        "products": results,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps({"checked": len(results), "counts": counts}, ensure_ascii=False))
    if len(results) != len(products):
        raise SystemExit("Not every published catalogue entry received a result.")


if __name__ == "__main__":
    main()
