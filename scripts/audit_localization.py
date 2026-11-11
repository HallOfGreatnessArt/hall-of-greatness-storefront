#!/usr/bin/env python3
"""Read-only localization inventory and structural QA for HALL OF GREATNESS.

This tool never edits locale files. It reports coverage, schema gaps, stale
product translations, possible English leftovers, RTL expectations, and review
evidence separately so technical completeness is not confused with quality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def canonical_ui(root: Path) -> dict[str, str]:
    source = (root / "assets/i18n.js").read_text(encoding="utf-8")
    match = re.search(r"const M=(\{[\s\S]*?\});\nconst map=", source)
    if not match:
        raise ValueError("Could not locate the canonical UI dictionary in assets/i18n.js")
    dictionaries = json.loads(match.group(1))
    if not isinstance(dictionaries.get("en"), dict):
        raise ValueError("Canonical English UI dictionary is missing")
    return dictionaries["en"]


def product_source_fields(product: dict[str, Any]) -> dict[str, Any]:
    fields = {
        key: product.get(key)
        for key in ("summary", "full_description", "category")
        if product.get(key)
    }
    fields["product_details"] = product.get("product_details") or {}
    return fields


def audit(root: Path) -> dict[str, Any]:
    registry = load_json(root / "locales/languages.json")
    languages = registry.get("languages", [])
    canonical = canonical_ui(root)
    catalog = load_json(root / "catalog-data.json")
    published = {
        item["permalink"]: item
        for item in catalog.get("products", [])
        if item.get("published") and item.get("permalink")
    }

    codes = [item.get("code") for item in languages]
    duplicate_codes = sorted({code for code in codes if codes.count(code) > 1})
    language_by_code = {item["code"]: item for item in languages if item.get("code")}
    locale_dir = root / "locales"
    locale_files = {
        path.stem: path
        for path in locale_dir.glob("*.json")
        if path.name != "languages.json"
    }
    expected_codes = {code for code in codes if code and code != "en"}
    missing_files = sorted(expected_codes - set(locale_files))
    unregistered_files = sorted(set(locale_files) - set(codes))
    rows: list[dict[str, Any]] = []

    for code in sorted(expected_codes | set(locale_files)):
        path = locale_files.get(code)
        language = language_by_code.get(code, {})
        row: dict[str, Any] = {
            "code": code,
            "name": language.get("name", code),
            "expected_rtl": bool(language.get("rtl", False)),
            "file_exists": path is not None,
            "technical_status": "missing" if path is None else "pending",
            "ui_review_status": "unreviewed",
            "products_review_status": "unreviewed",
            "issues": [],
            "counts": {},
        }
        if path is None:
            row["issues"].append("locale_file_missing; runtime may fall back to English")
            rows.append(row)
            continue
        try:
            data = load_json(path)
        except Exception as exc:
            row["technical_status"] = "fail"
            row["issues"].append(f"invalid_json: {exc}")
            rows.append(row)
            continue

        if not isinstance(data, dict):
            row["technical_status"] = "fail"
            row["issues"].append("locale_root_must_be_object")
            rows.append(row)
            continue

        ui = data.get("ui") or {}
        products = data.get("products") or {}
        if not isinstance(ui, dict):
            ui = {}
            row["issues"].append("ui_section_must_be_object")
        if not isinstance(products, dict):
            products = {}
            row["issues"].append("products_section_must_be_object")

        missing_ui = sorted(set(canonical) - set(ui))
        extra_ui = sorted(set(ui) - set(canonical))
        blank_ui = sorted(
            key for key, value in ui.items()
            if not isinstance(value, str) or not value.strip()
        )
        english_ui = sorted(
            key for key, value in ui.items()
            if key in canonical and isinstance(value, str) and value == canonical[key]
        )
        missing_products = sorted(set(published) - set(products))
        stale_products = []
        missing_product_fields = []
        english_product_fields = []
        for permalink, product in published.items():
            translated = products.get(permalink)
            if not isinstance(translated, dict):
                continue
            source_hash = digest(product_source_fields(product))
            if translated.get("_source_hash") != source_hash:
                stale_products.append(permalink)
            for field in ("summary", "full_description", "category"):
                source_value = product.get(field)
                translated_value = translated.get(field)
                if source_value and not translated_value:
                    missing_product_fields.append(f"{permalink}:{field}")
                elif source_value and translated_value == source_value:
                    english_product_fields.append(f"{permalink}:{field}")
            source_details = product.get("product_details") or {}
            translated_details = translated.get("product_details") or {}
            for detail_key, source_value in source_details.items():
                translated_value = translated_details.get(detail_key)
                if source_value and not translated_value:
                    missing_product_fields.append(f"{permalink}:product_details.{detail_key}")
                elif source_value and translated_value == source_value:
                    english_product_fields.append(f"{permalink}:product_details.{detail_key}")

        ui_reviewed = data.get("_ui_reviewed") is True and bool(ui)
        products_reviewed = data.get("_products_reviewed") is True and bool(products)
        row["ui_review_status"] = "editorially-reviewed" if ui_reviewed else "unreviewed"
        row["products_review_status"] = "editorially-reviewed" if products_reviewed else "unreviewed"
        row["counts"] = {
            "ui_keys": len(ui),
            "canonical_ui_keys": len(canonical),
            "missing_ui_keys": len(missing_ui),
            "extra_ui_keys": len(extra_ui),
            "blank_ui_values": len(blank_ui),
            "ui_values_identical_to_english": len(english_ui),
            "published_products_expected": len(published),
            "products_present": len(products),
            "missing_products": len(missing_products),
            "stale_product_translations": len(stale_products),
            "missing_product_fields": len(missing_product_fields),
            "product_fields_identical_to_english": len(english_product_fields),
        }
        row["details"] = {
            "missing_ui_keys": missing_ui,
            "extra_ui_keys": extra_ui,
            "blank_ui_values": blank_ui,
            "ui_values_identical_to_english": english_ui,
            "missing_products": missing_products,
            "stale_product_translations": stale_products,
            "missing_product_fields": missing_product_fields,
            "product_fields_identical_to_english": english_product_fields,
        }
        if missing_ui or blank_ui or missing_products or missing_product_fields:
            row["issues"].append("translation_content_incomplete")
        if extra_ui:
            row["issues"].append("unexpected_ui_keys")
        if stale_products:
            row["issues"].append("product_translation_out_of_date")
        if english_ui or english_product_fields:
            row["issues"].append("possible_english_fallback_or_untranslated_content")
        row["technical_status"] = "pass"
        row["translation_status"] = "incomplete" if any((missing_ui, blank_ui, missing_products, stale_products, missing_product_fields)) else "structurally-complete"
        if extra_ui:
            row["technical_status"] = "warning"
        row["rtl_runtime_test_required"] = row["expected_rtl"]
        rows.append(row)

    summary = {
        "registered_languages": len(languages),
        "unique_language_codes": len(set(codes)),
        "duplicate_language_codes": duplicate_codes,
        "canonical_ui_keys": len(canonical),
        "published_products": len(published),
        "locale_files": len(locale_files),
        "missing_locale_files": len(missing_files),
        "unregistered_locale_files": len(unregistered_files),
        "editorially_reviewed_ui": sum(x["ui_review_status"] == "editorially-reviewed" for x in rows),
        "editorially_reviewed_products": sum(x["products_review_status"] == "editorially-reviewed" for x in rows),
        "ui_values_identical_to_english": sum(x["counts"].get("ui_values_identical_to_english", 0) for x in rows),
        "product_fields_identical_to_english": sum(x["counts"].get("product_fields_identical_to_english", 0) for x in rows),
        "stale_product_translations": sum(x["counts"].get("stale_product_translations", 0) for x in rows),
        "missing_product_fields": sum(x["counts"].get("missing_product_fields", 0) for x in rows),
        "rtl_languages_requiring_runtime_tests": sum(bool(x.get("rtl_runtime_test_required")) for x in rows),
        "technical_pass": sum(x["technical_status"] == "pass" for x in rows),
        "technical_warning": sum(x["technical_status"] == "warning" for x in rows),
        "technical_fail": sum(x["technical_status"] == "fail" for x in rows),
        "translation_incomplete": sum(x.get("translation_status") == "incomplete" for x in rows),
        "missing": sum(x["technical_status"] == "missing" for x in rows),
    }
    return {
        "report_version": 1,
        "read_only": True,
        "summary": summary,
        "missing_locale_codes": missing_files,
        "unregistered_locale_codes": unregistered_files,
        "languages": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--format", choices=("json", "summary"), default="json")
    args = parser.parse_args()
    try:
        report = audit(args.root)
    except Exception as exc:
        print(f"Localization audit failed: {exc}", file=sys.stderr)
        return 2
    if args.format == "summary":
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["summary"]["duplicate_language_codes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
