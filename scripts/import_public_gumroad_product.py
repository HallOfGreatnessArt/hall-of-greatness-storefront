#!/usr/bin/env python3
"""Import one public Gumroad product, including its public description and buyer details, without OAuth.
Version: full-description-test-2."""
from __future__ import annotations
import argparse, html, json, re, sys, urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

STORE_HOST = "alshayebemad.gumroad.com"

class ProductPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.title_parts = []
        self.in_title = False
        self.json_ld = []
        self.in_json = False
        self.script_parts = []
        self.article_depth = 0
        self.paragraph_depth = 0
        self.paragraph_parts = []
        self.paragraphs = []
        self.article_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        tag = tag.lower()
        if tag == "meta":
            key = attrs.get("property") or attrs.get("name") or attrs.get("itemprop")
            value = attrs.get("content")
            if key and value:
                self.meta[key.lower()] = html.unescape(value.strip())
        elif tag == "title":
            self.in_title = True
        elif tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self.in_json = True
            self.script_parts = []
        elif tag == "article":
            self.article_depth += 1
        elif tag == "p" and self.article_depth:
            if self.paragraph_depth == 0:
                self.paragraph_parts = []
            self.paragraph_depth += 1

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self.in_title = False
        elif tag == "script" and self.in_json:
            self.json_ld.append("".join(self.script_parts))
            self.in_json = False
            self.script_parts = []
        elif tag == "p" and self.article_depth and self.paragraph_depth:
            self.paragraph_depth -= 1
            if self.paragraph_depth == 0:
                value = clean(" ".join(self.paragraph_parts))
                if value:
                    self.paragraphs.append(value)
        elif tag == "article" and self.article_depth:
            self.article_depth -= 1

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        if self.in_json:
            self.script_parts.append(data)
        if self.article_depth:
            self.article_parts.append(data)
        if self.article_depth and self.paragraph_depth:
            self.paragraph_parts.append(data)

def clean(value):
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()

def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)

def schema_product(parser):
    for raw in parser.json_ld:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for obj in walk(parsed):
            kind = obj.get("@type", [])
            kind = [kind] if isinstance(kind, str) else kind
            if any(str(item).lower() == "product" for item in kind):
                return obj
    return {}

def slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "new-artwork"

def category_for(name, description):
    value = f"{name} {description}".lower()
    if any(word in value for word in ("egypt", "egyptian", "nile", "coptic", "roman", "heritage", "pharaoh")):
        return "Heritage"
    if any(word in value for word in ("humanity", "compassion", "generation", "child", "earth", "hands", "hope", "legacy", "tree", "friendship", "love")):
        return "Humanity"
    if any(word in value for word in ("elegance", "serenity", "peace", "golden", "luxury", "celestial", "garden", "grace")):
        return "Elegance"
    return "Global"

def fetch_public_page(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != STORE_HOST or not parsed.path.startswith("/l/"):
        raise ValueError(f"Only public product URLs on https://{STORE_HOST}/l/... are allowed")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError("Playwright is required for rendered public product-page extraction") from error
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.locator("main").wait_for(state="visible", timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        final_url = page.url
        if urlparse(final_url).hostname != STORE_HOST:
            browser.close()
            raise ValueError("The product URL redirected outside the approved Gumroad storefront")
        rendered_text = page.locator("main").inner_text(timeout=15000)
        article_h2 = page.locator("main article h2").all_text_contents()
        article_h4 = page.locator("main article h4").all_text_contents()
        body = page.content()
        browser.close()
    if response is not None and response.status >= 400:
        raise ValueError(f"Public product page returned HTTP {response.status}")
    parser = ProductPageParser()
    parser.feed(body)
    return parser, final_url, rendered_text, article_h2, article_h4

def detail_between(text, start, end):
    pattern = rf"{re.escape(start)}\s*:?\s*(.*?)(?={re.escape(end)}\s*:?\s*|$)"
    match = re.search(pattern, text, flags=re.I | re.S)
    return clean(match.group(1)) if match else ""

def extract_full_description(parser, rendered_text, article_h2=None):
    if rendered_text:
        text = rendered_text
        if "This bundle contains" in text and article_h2:
            description_heading = next((heading for heading in reversed(article_h2) if heading.strip()), "")
            if description_heading and description_heading in text:
                text = text.split(description_heading, 1)[1]
                text = description_heading + "\\n" + text
        if "Add to wishlist" in text:
            text = text.split("Add to wishlist", 1)[1]
        for marker in ("EXPLORE OUR COLLECTION", "More from this creator"):
            if marker in text:
                text = text.split(marker, 1)[0]
        lines = [clean(line) for line in text.splitlines()]
        excluded = ("i want this!", "already bought this?", "add to wishlist", "https://schema.org/")
        candidates = [
            line for line in lines
            if line and line.lower() not in ("usd", "in stock")
            and not line.startswith("$")
            and not any(token in line.lower() for token in excluded)
        ]
        return "\n\n".join(dict.fromkeys(candidates)).strip()
    excluded = (
        "https://schema.org/", "already bought this?", "i want this!", "add to wishlist",
        "product type", "delivery", "physical item", "printing", "usage",
    )
    candidates = []
    for paragraph in parser.paragraphs:
        value = clean(paragraph)
        if not value or value.lower() in ("usd", "in stock") or value.startswith("$"):
            continue
        if any(token in value.lower() for token in excluded):
            continue
        if re.match(r"^\d+\s+file\b", value, re.I) or value.lower().startswith("includes:"):
            continue
        candidates.append(value)
    return "\n\n".join(dict.fromkeys(candidates)).strip()

def normalize_title(value):
    return re.sub(r"[^a-z0-9]+", " ", clean(value).lower()).strip()

def resolve_bundle_items(item_names, full_description, products):
    names = list(item_names)
    if "WHAT'S INCLUDED" in full_description.upper():
        section = re.split(r"WHAT'S INCLUDED", full_description, flags=re.I, maxsplit=1)[1]
        section = re.split(r"WHERE IT BELONGS|DIGITAL DOWNLOAD|WHY YOU", section, flags=re.I, maxsplit=1)[0]
        names.extend(line.strip(" •-–") for line in section.splitlines() if line.strip())
    resolved = []
    unresolved = []
    seen = set()
    for name in names:
        candidate = normalize_title(name)
        if not candidate or candidate in {"qty 1", "0 0 0"} or re.fullmatch(r"\$?\d+(?:\.\d+)?", candidate):
            continue
        match = next((p for p in products if candidate in normalize_title(p.get("name", "")) or normalize_title(p.get("name", "")) in candidate), None)
        if match:
            permalink = match.get("permalink")
            if permalink and permalink not in seen:
                resolved.append(permalink)
                seen.add(permalink)
        elif name not in unresolved and len(candidate.split()) >= 2:
            unresolved.append(clean(name))
    return resolved, unresolved

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--catalog", default="catalog-data.json")
    args = ap.parse_args()

    parser, final_url, rendered_text, article_h2, article_h4 = fetch_public_page(args.url)
    meta = parser.meta
    schema = schema_product(parser)

    name = clean(meta.get("og:title") or meta.get("twitter:title") or schema.get("name") or "".join(parser.title_parts))
    summary = clean(meta.get("og:description") or meta.get("description") or schema.get("description"))
    image = meta.get("og:image") or meta.get("twitter:image")
    if not image:
        schema_image = schema.get("image")
        image = schema_image if isinstance(schema_image, str) else (schema_image[0] if isinstance(schema_image, list) and schema_image else "")
    match = re.search(r"/l/([^/?#]+)", final_url)
    permalink = meta.get("product:retailer_item_id") or (match.group(1) if match else "")
    raw_price = meta.get("product:price:amount")
    currency = meta.get("product:price:currency", "USD").upper()
    if not raw_price and isinstance(schema.get("offers"), dict):
        raw_price = str(schema["offers"].get("price", ""))
        currency = str(schema["offers"].get("priceCurrency", currency)).upper()

    is_bundle = "This bundle contains" in rendered_text\n    full_description = extract_full_description(parser, rendered_text, article_h2)
    article_text = clean(rendered_text or " ".join(parser.article_parts))
    product_details = {
        "files_included": "",
        "product_type": detail_between(article_text, "Product type", "Delivery"),
        "delivery": detail_between(article_text, "Delivery", "Physical item"),
        "physical_item": detail_between(article_text, "Physical item", "Printing"),
        "printing": detail_between(article_text, "Printing", "Usage"),
        "usage": detail_between(article_text, "Usage", "Add to wishlist"),
    }
    includes_match = re.search(r"Includes:\s*(.*?)(?=I want this!|Already bought this\?|Product type|$)", article_text, re.I)
    if includes_match:
        product_details["files_included"] = clean(includes_match.group(1))\n    if is_bundle:\n        product_details["bundle_item_count"] = "Bundle collection; individual artworks listed below"
    product_details = {key: value for key, value in product_details.items() if value}

    missing = [key for key, value in {
        "product name": name, "short summary": summary, "cover image": image,
        "product identifier": permalink, "price": raw_price, "full description": full_description,
    }.items() if not value]
    if missing:
        raise ValueError("Public page did not expose required fields: " + ", ".join(missing))
    if currency != "USD":
        raise ValueError(f"Expected USD product price, found {currency}")

    data = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    existing = next((product for product in data["products"] if product.get("permalink") == permalink), None)
    if existing:
        print(json.dumps({"status": "already_present", "product": existing}, ensure_ascii=False, indent=2))
        return

    slug = slugify(name)
    used_slugs = {product.get("landing_slug") for product in data["products"]}
    base_slug, suffix = slug, 2
    while slug in used_slugs:
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    bundle_contents, bundle_item_names = resolve_bundle_items(article_h4, full_description, data["products"]) if is_bundle else ([], [])\n    product = {\n        "name": name,
        "price_usd": float(raw_price),
        "url": final_url,
        "permalink": permalink,
        "published": True,
        "is_bundle": is_bundle,\n        "bundle_contents": bundle_contents,\n        "bundle_item_names": bundle_item_names,
        "category": category_for(name, full_description),
        "landing_slug": slug,
        "cover_url": image,
        "summary": summary[:420],
        "full_description": full_description,
        "product_details": product_details,
        "description_source": "Public Gumroad product page; no OAuth",
    }
    data["products"].append(product)
    data["product_count"] = len(data["products"])
    data["source"] = "Public Gumroad product page (no OAuth)"
    Path(args.catalog).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "imported", "product": product}, ensure_ascii=False, indent=2))
    print("PUBLIC_GUMROAD_IMPORT_OK")

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"PUBLIC_GUMROAD_IMPORT_FAILED: {error}", file=sys.stderr)
        raise
