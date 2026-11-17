#!/usr/bin/env python3
"""Apply curated product-type metadata to the public Gumroad catalogue.

Gumroad's public product feed does not consistently expose tags. This small,
version-controlled registry is therefore the source of truth for editorial
classification. New books are registered by exact Gumroad permalink; the
resulting tags are embedded in catalog-data.json for every downstream gallery.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "catalog-data.json"
CLASSIFICATIONS_PATH = ROOT / "product-classifications.json"


def apply_classifications(catalog: dict, manifest: dict) -> int:
    products = catalog.get("products")
    classifications = manifest.get("products")
    if not isinstance(products, list) or not isinstance(classifications, dict):
        raise ValueError("Catalogue products and classification manifest products must be valid objects")

    by_permalink = {
        str(product.get("permalink", "")).strip(): product
        for product in products
        if isinstance(product, dict) and product.get("permalink")
    }
    missing = sorted(set(classifications) - set(by_permalink))
    if missing:
        raise ValueError("Classification manifest references unknown catalogue permalinks: " + ", ".join(missing))

    applied = 0
    for permalink, classification in classifications.items():
        if not isinstance(classification, dict):
            raise ValueError(f"Invalid classification for {permalink}")
        product = by_permalink[permalink]
        if product.get("published") is not True or product.get("archived") is True:
            continue
        content_type = classification.get("content_type")
        tags = classification.get("tags", [])
        if not isinstance(content_type, str) or not content_type.strip():
            raise ValueError(f"Missing content_type for {permalink}")
        if not isinstance(tags, list) or not all(isinstance(tag, str) and tag.strip() for tag in tags):
            raise ValueError(f"Invalid tags for {permalink}")
        existing = product.get("tags", [])
        if not isinstance(existing, list):
            raise ValueError(f"Existing tags must be a list for {permalink}")
        merged = list(dict.fromkeys([*existing, *tags]))
        product["tags"] = merged
        product["content_type"] = content_type.strip().lower()
        applied += 1
    return applied


def main() -> int:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(CLASSIFICATIONS_PATH.read_text(encoding="utf-8"))
    applied = apply_classifications(catalog, manifest)
    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Applied curated classifications to {applied} published product(s).")
    ebooks = [
        product for product in catalog["products"]
        if product.get("published") is True and "ebooks" in product.get("tags", [])
    ]
    print("Published EBOOKS LIBRARY products: " + ", ".join(
        f'{product.get("name")} ({product.get("permalink")})' for product in ebooks
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
