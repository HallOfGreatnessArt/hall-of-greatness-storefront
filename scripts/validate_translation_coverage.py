#!/usr/bin/env python3
"""Fail the build if any registered storefront language has incomplete page copy."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from translate_landing_pages import extract_page_copy


def load_sources(root: Path):
    registry = json.loads((root / "locales/languages.json").read_text(encoding="utf-8"))
    catalog = json.loads((root / "catalog-data.json").read_text(encoding="utf-8"))
    landing_copy = json.loads((root / "assets/landing-copy.json").read_text(encoding="utf-8"))
    detail_labels = {
        "files_included": "Files included",
        "product_type": "Product type",
        "delivery": "Delivery",
        "physical_item": "Physical item",
        "printing": "Printing",
        "usage": "Usage",
        "bundle_item_count": "Items in bundle",
    }
    i18n_source = (root / "assets/i18n.js").read_text(encoding="utf-8")
    match = re.search(r"const M=(\{[\s\S]*?\});\nconst map=", i18n_source)
    if not match:
        raise RuntimeError("Cannot read canonical UI dictionary from assets/i18n.js")
    ui = json.loads(match.group(1))["en"]
    products = [item for item in catalog["products"] if item.get("published")]
    titles = [str(item.get("name", "")).strip() for item in catalog["products"]]
    titles.append("HALL OF GREATNESS")
    return registry, ui, landing_copy, products, titles


def validate(root: Path):
    registry, ui, landing_copy, products, titles = load_sources(root)
    failures = []
    completed = []
    for language in registry.get("languages", []):
        code = language.get("code")
        if not code or code == "en":
            continue
        path = root / "locales" / f"{code}.json"
        if not path.is_file():
            failures.append(f"{code}: missing locale file")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            failures.append(f"{code}: invalid locale JSON ({exc})")
            continue

        missing_ui = [key for key in ui if not isinstance(data.get("ui", {}).get(key), str) or not data["ui"][key].strip()]
        missing_landing_ui = [key for key in landing_copy if not isinstance(data.get("landing_ui", {}).get(key), str) or not data["landing_ui"][key].strip()]
        missing_detail_labels = [key for key in detail_labels if not isinstance(data.get("product_detail_labels", {}).get(key), str) or not data["product_detail_labels"][key].strip()]
        missing_products = []
        missing_page_copy = []
        for product in products:
            permalink = product["permalink"]
            item = data.get("products", {}).get(permalink, {})
            for field in ("summary", "full_description", "category"):
                if product.get(field) and (not isinstance(item.get(field), str) or not item[field].strip()):
                    missing_products.append(f"{permalink}:{field}")
            expected_details = [key for key, value in (product.get("product_details") or {}).items() if value]
            translated_details = item.get("product_details", {})
            for key in expected_details:
                if not isinstance(translated_details.get(key), str) or not translated_details[key].strip():
                    missing_products.append(f"{permalink}:product_details.{key}")

            page_path = root / "landing" / product["landing_slug"] / "index.html"
            page_html = page_path.read_text(encoding="utf-8") if page_path.is_file() else ""
            source_texts = extract_page_copy(page_html, titles)
            page_map = data.get("landing_pages", {}).get(permalink, {})
            for source_text in source_texts:
                if not isinstance(page_map.get(source_text), str) or not page_map[source_text].strip():
                    missing_page_copy.append(f"{permalink}:{source_text[:70]}")

        if missing_ui or missing_landing_ui or missing_detail_labels or missing_products or missing_page_copy:
            if missing_ui:
                failures.append(f"{code}: {len(missing_ui)} shared UI translations missing")
            if missing_landing_ui:
                failures.append(f"{code}: {len(missing_landing_ui)} shared product-page translations missing")
            if missing_detail_labels:
                failures.append(f"{code}: {len(missing_detail_labels)} product-detail labels missing")
            if missing_products:
                failures.append(f"{code}: {len(missing_products)} catalogue fields missing")
            if missing_page_copy:
                failures.append(f"{code}: {len(missing_page_copy)} artwork-specific page strings missing")
        else:
            completed.append(code)

    report = {
        "registered_languages": len(registry.get("languages", [])),
        "non_english_languages": len(registry.get("languages", [])) - 1,
        "complete_languages": len(completed),
        "incomplete_languages": len(registry.get("languages", [])) - 1 - len(completed),
        "complete_locale_codes": completed,
        "failures": failures,
        "published_products_checked": len(products),
        "shared_ui_keys_checked": len(ui),
        "shared_product_page_keys_checked": len(landing_copy),
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    report = validate(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["failures"]:
        raise SystemExit(1)
    print(f"Complete translation coverage verified for {report['complete_languages']} non-English languages.")


if __name__ == "__main__":
    main()
