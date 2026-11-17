#!/usr/bin/env python3
"""Read published Gumroad products and synchronize section tags into the storefront catalogue.

This script is read-only against Gumroad. It appends new published products and
refreshes only the local catalogue tag field for known products; it never writes
products, prices, files, publication state, or account settings back to Gumroad.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "catalog-data.json"
API_URL = "https://api.gumroad.com/v2/products"
STORE_BASE = "https://alshayebemad.gumroad.com/l/"


def clean_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def slugify(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "new-artwork"


def infer_category(product: dict) -> str:
    haystack = " ".join([
        str(product.get("name", "")),
        str(product.get("description", "")),
        " ".join(map(str, product.get("tags") or [])),
    ]).lower()

    if any(word in haystack for word in (
        "coptic", "egypt", "egyptian", "nile", "pharaoh", "roman",
        "ancient", "heritage", "civilization", "temple",
    )):
        return "Heritage"
    if any(word in haystack for word in (
        "human", "humanity", "compassion", "generation", "love", "bond",
        "child", "mother", "family", "earth", "shelter", "hands",
        "tenderness", "legacy", "hope", "friendship", "tree",
    )):
        return "Humanity"
    if any(word in haystack for word in (
        "elegance", "serenity", "stillness", "peace", "golden", "luxury",
        "abstract", "meditation", "celestial", "garden", "silence",
        "marble", "calm", "grace",
    )):
        return "Elegance"
    return "Global"


def extract_summary(product: dict) -> str:
    summary = clean_text(product.get("summary"))
    if summary:
        return summary
    description = str(product.get("description") or "")
    blocks = [clean_text(part) for part in re.split(r"(?:\r?\n){2,}|</p>|<br\s*/?>", description, flags=re.I)]
    blocks = [part for part in blocks if len(part) >= 35]
    if blocks:
        return blocks[0][:420]
    return ""


def extract_cover(product: dict) -> str:
    for key in ("thumbnail_url", "cover_url", "preview_url"):
        value = product.get(key)
        if isinstance(value, str) and value.startswith("https://"):
            return value
    covers = product.get("covers") or []
    if covers and isinstance(covers[0], dict):
        value = covers[0].get("url")
        if isinstance(value, str) and value.startswith("https://"):
            return value
    return ""


def extract_permalink(product: dict) -> str:
    # Prefer Gumroad's public product URL; custom_permalink is only a fallback.
    for key in ("short_url", "url"):
        value = product.get(key)
        if isinstance(value, str):
            path = urlparse(value).path.rstrip("/")
            if "/l/" in path:
                return path.split("/l/", 1)[1]
    value = product.get("permalink") or product.get("custom_permalink")
    return str(value).strip().strip("/") if value else ""


def product_url(product: dict, permalink: str) -> str:
    for key in ("short_url", "url"):
        value = product.get(key)
        if isinstance(value, str) and value.startswith("https://"):
            return value
    return STORE_BASE + permalink


def product_identity_url(value: object) -> str:
    """Return a stable Gumroad product path for duplicate detection."""
    if not isinstance(value, str) or not value.startswith("https://"):
        return ""
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if host == "gumroad.com" or host.endswith(".gumroad.com"):
        return parsed.path.rstrip("/").lower()
    return ""



def normalize_gumroad_tags(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, dict):
            item = item.get("name")
        if isinstance(item, str) and item.strip():
            tag = item.strip().lower().replace("_", "-").replace(" ", "-")
            if tag not in result:
                result.append(tag)
    return result


def price_in_usd(product: dict) -> float:
    currency = str(product.get("currency") or "usd").lower()
    if currency != "usd":
        raise ValueError(f"unsupported currency {currency!r}; storefront pricing is currently USD")
    raw = product.get("price_cents", product.get("price"))
    if raw is None:
        raise ValueError("Gumroad API response has no price/price_cents field")
    return round(float(raw) / 100.0, 2)


def build_record(product: dict, used_slugs: set[str]) -> dict:
    name = clean_text(product.get("name"))
    permalink = extract_permalink(product)
    cover = extract_cover(product)
    summary = extract_summary(product)
    if not name or not permalink or not cover or not summary:
        missing = [label for label, value in (
            ("name", name), ("permalink", permalink), ("cover image", cover), ("summary/description", summary)
        ) if not value]
        raise ValueError(f"{name or 'Unnamed product'}: missing {', '.join(missing)}")
    if product.get("published") is not True:
        raise ValueError("product is not published")

    base = slugify(name)
    slug = base
    if slug in used_slugs:
        slug = f"{base}-{slugify(permalink)}"
    if slug in used_slugs:
        raise ValueError(f"could not create a unique landing slug for {name}")

    is_bundle = bool(product.get("is_bundle", False))
    bundle_contents = product.get("bundle_contents") or product.get("bundle_products")
    if is_bundle and not (isinstance(bundle_contents, list) and bundle_contents):
        raise ValueError("bundle contents were not supplied by the product-list response; skipping until verified")
    record = {
        "name": name,
        "price_usd": price_in_usd(product),
        "url": product_url(product, permalink),
        "permalink": permalink,
        "published": True,
        "is_bundle": is_bundle,
        "category": infer_category(product),
        "landing_slug": slug,
        "cover_url": cover,
        "summary": summary,
    }
    incoming_tags = normalize_gumroad_tags(product.get("tags"))
    if incoming_tags:
        record["tags"] = incoming_tags
    if is_bundle:
        record["bundle_contents"] = [
            item.get("permalink") if isinstance(item, dict) else str(item)
            for item in bundle_contents
        ]
    return record


def fetch_products(token: str) -> list[dict]:
    request = urllib.request.Request(
        API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "HALL-OF-GREATNESS-storefront-sync/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Gumroad API returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Gumroad API: {exc}") from exc

    if payload.get("success") is not True:
        raise RuntimeError(f"Gumroad API did not confirm success: {payload}")
    products = payload.get("products")
    if not isinstance(products, list):
        raise RuntimeError("Gumroad API response did not contain a products list")
    return products


def sync(products: list[dict], catalog: dict) -> tuple[list[str], list[str]]:
    existing = catalog.setdefault("products", [])
    by_permalink = {
        str(p.get("permalink", "")).strip().lower(): p
        for p in existing if p.get("permalink")
    }
    by_url = {
        product_identity_url(p.get("url")): p
        for p in existing if product_identity_url(p.get("url"))
    }
    used_slugs = {str(p.get("landing_slug")) for p in existing if p.get("landing_slug")}
    added: list[str] = []
    tag_updates: list[str] = []

    for product in products:
        if product.get("published") is not True:
            continue
        permalink = extract_permalink(product)
        incoming_url = product_identity_url(product_url(product, permalink)) if permalink else ""
        current = by_permalink.get(permalink.strip().lower()) if permalink else None
        if current is None and incoming_url:
            current = by_url.get(incoming_url)

        # Keep current product content and presentation untouched; synchronize
        # only the tags that the owner configured in Gumroad product settings.
        if current is not None:
            incoming_tags = normalize_gumroad_tags(product.get("tags"))
            if incoming_tags and current.get("tags") != incoming_tags:
                current["tags"] = incoming_tags
                tag_updates.append(str(current.get("name") or permalink))
            continue

        if not permalink:
            continue
        try:
            record = build_record(product, used_slugs)
        except ValueError as exc:
            print(f"::warning::Skipping {product.get('name', permalink)}: {exc}")
            continue
        existing.append(record)
        by_permalink[permalink.strip().lower()] = record
        record_url_identity = product_identity_url(record.get("url"))
        if record_url_identity:
            by_url[record_url_identity] = record
        used_slugs.add(record["landing_slug"])
        added.append(record["name"])

    catalog["product_count"] = len(existing)
    catalog["verified_at"] = dt.datetime.now(dt.timezone.utc).date().isoformat()
    return added, tag_updates

def main() -> int:
    token = os.environ.get("GUMROAD_ACCESS_TOKEN", "").strip()
    if not token:
        print("::warning::GUMROAD_ACCESS_TOKEN is not configured. Sync was skipped; add it in GitHub Actions repository secrets to enable automatic discovery.")
        return 0

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    gumroad_products = fetch_products(token)
    added, tag_updates = sync(gumroad_products, catalog)

    if added or tag_updates:
        CATALOG_PATH.write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"Added {len(added)} newly published Gumroad product(s).")
    print(f"Refreshed Gumroad tag metadata for {len(tag_updates)} existing product(s).")
    if tag_updates:
        for name in tag_updates:
            print(f" - tags refreshed: {name}")
    print(f"Catalogue now contains {len(catalog['products'])} products.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"::error::{exc}")
        raise
