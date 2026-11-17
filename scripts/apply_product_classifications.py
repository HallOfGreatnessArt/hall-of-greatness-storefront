#!/usr/bin/env python3
"""Classify published Gumroad catalogue products into the three storefront sections.

Gumroad API tags are authoritative when they identify a section. The exact-
permalink manifest is a compatibility fallback for the already-published
catalogue and for legacy products whose public feed omits tags.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "catalog-data.json"
CLASSIFICATIONS_PATH = ROOT / "product-classifications.json"

TAG_TYPES = {
    "art-decor": "art-decor",
    "art": "art-decor",
    "decor": "art-decor",
    "decoration": "art-decor",
    "wall-art": "art-decor",
    "printable-art": "art-decor",
    "ebooks": "ebook",
    "ebook": "ebook",
    "e-book": "ebook",
    "digital-ebook": "ebook",
    "digital-book": "ebook",
    "courses": "course",
    "course": "course",
    "online-course": "course",
    "educational-course": "course",
    "training": "course",
}
CANONICAL_TAG = {"art-decor": "art-decor", "ebook": "ebooks", "course": "courses"}
VALID_TYPES = set(CANONICAL_TAG)


def normalize_tags(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("Product tags must be a list")
    result = []
    for item in value:
        if isinstance(item, dict):
            item = item.get("name")
        if isinstance(item, str) and item.strip():
            tag = item.strip().lower().replace("_", "-").replace(" ", "-")
            if tag not in result:
                result.append(tag)
    return result


def type_from_tags(tags: list[str]) -> str | None:
    found = {TAG_TYPES[tag] for tag in tags if tag in TAG_TYPES}
    if len(found) > 1:
        raise ValueError("Conflicting section tags: " + ", ".join(sorted(found)))
    return next(iter(found), None)


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
    for product in products:
        if not isinstance(product, dict) or product.get("published") is not True or product.get("archived") is True:
            continue
        permalink = str(product.get("permalink", "")).strip()
        tags = normalize_tags(product.get("tags", []))
        tagged_type = type_from_tags(tags)
        fallback = classifications.get(permalink)
        fallback_type = None
        fallback_tags = []
        if fallback is not None:
            if not isinstance(fallback, dict):
                raise ValueError(f"Invalid classification for {permalink}")
            fallback_type = str(fallback.get("content_type", "")).strip().lower()
            if fallback_type not in VALID_TYPES:
                raise ValueError(f"Invalid content_type for {permalink}: {fallback_type}")
            fallback_tags = normalize_tags(fallback.get("tags", []))
            if fallback_tags and type_from_tags(fallback_tags) != fallback_type:
                raise ValueError(f"Manifest tags do not match content_type for {permalink}")

        # Real Gumroad tags take precedence over the legacy curated fallback.
        content_type = tagged_type or fallback_type
        if content_type is None:
            product.pop("content_type", None)
            continue

        canonical = CANONICAL_TAG[content_type]
        if canonical not in tags:
            tags.append(canonical)
        product["tags"] = tags
        product["content_type"] = content_type
        applied += 1
    return applied


def main() -> int:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(CLASSIFICATIONS_PATH.read_text(encoding="utf-8"))
    applied = apply_classifications(catalog, manifest)
    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {kind: sum(p.get("published") is True and p.get("content_type") == kind for p in catalog["products"])
              for kind in sorted(VALID_TYPES)}
    print(f"Classified {applied} published product(s): " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    unclassified = [p.get("permalink") for p in catalog["products"] if p.get("published") is True and p.get("content_type") not in VALID_TYPES]
    print("Unclassified published products (not displayed in a section): " + (", ".join(map(str, unclassified)) or "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
