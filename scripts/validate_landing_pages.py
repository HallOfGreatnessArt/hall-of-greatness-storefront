#!/usr/bin/env python3
"""Strict structural checks for every published HALL OF GREATNESS landing page."""
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://hallofgreatnessart.github.io/hall-of-greatness-storefront/"


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.starts = {}
        self.ends = {}
        self.ids = []
        self.body_attrs = {}
        self.titles = []
        self.in_title = False
        self.title_parts = []
        self.local_scripts = []
        self.images_without_alt = []

    def handle_starttag(self, tag, attrs):
        self.starts[tag] = self.starts.get(tag, 0) + 1
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag == "body":
            self.body_attrs = attrs
        if tag == "title":
            self.in_title = True
            self.title_parts = []
        if tag == "script" and attrs.get("src"):
            self.local_scripts.append(attrs["src"])
        if tag == "img" and not attrs.get("alt"):
            self.images_without_alt.append(attrs.get("src", "(missing src)"))

    def handle_endtag(self, tag):
        self.ends[tag] = self.ends.get(tag, 0) + 1
        if tag == "title":
            self.in_title = False
            self.titles.append("".join(self.title_parts).strip())

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)


def fail(message):
    raise SystemExit("LANDING VALIDATION FAILED: " + message)


catalog = json.loads((ROOT / "catalog-data.json").read_text(encoding="utf-8"))
published = [p for p in catalog.get("products", []) if p.get("published") is True]
expected_slugs = {p["landing_slug"] for p in published}
actual_paths = sorted((ROOT / "landing").glob("*/index.html"))
actual_slugs = {p.parent.name for p in actual_paths}

if len(expected_slugs) != len(published):
    fail("catalogue contains duplicate landing slugs")
if actual_slugs != expected_slugs:
    fail(
        f"landing-page/catalogue mismatch; missing={sorted(expected_slugs-actual_slugs)}, "
        f"unexpected={sorted(actual_slugs-expected_slugs)}"
    )

for product in published:
    path = ROOT / "landing" / product["landing_slug"] / "index.html"
    page = path.read_text(encoding="utf-8")
    if "</script>\\n" in page or "\\n</body>" in page or "\\n</html>" in page:
        fail(f"literal backslash-n leaked into markup: {path}")

    parser = PageParser()
    try:
        parser.feed(page)
        parser.close()
    except Exception as exc:
        fail(f"HTML parser error in {path}: {exc}")

    for tag in ("html", "head", "body"):
        if parser.starts.get(tag, 0) != 1 or parser.ends.get(tag, 0) != 1:
            fail(
                f"{path}: expected one opening and closing <{tag}>; "
                f"found {parser.starts.get(tag, 0)} / {parser.ends.get(tag, 0)}"
            )
    if parser.body_attrs.get("data-product-permalink") != product.get("permalink"):
        fail(f"{path}: body product permalink does not match catalogue")
    if len(parser.titles) != 1 or not parser.titles[0]:
        fail(f"{path}: missing or duplicate document title")
    duplicates = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
    if duplicates:
        fail(f"{path}: duplicate element IDs: {duplicates}")
    if parser.images_without_alt:
        fail(f"{path}: images missing alt text: {parser.images_without_alt}")
    if product["cover_url"] not in page:
        fail(f"{path}: catalogue cover URL is missing")
    if product["url"] not in page:
        fail(f"{path}: exact Gumroad product URL is missing")
    if 'rel="canonical"' not in page or 'name="description"' not in page:
        fail(f"{path}: missing canonical or meta description")
    if 'id="printing"' not in page or 'id="room-showcase"' not in page:
        fail(f"{path}: missing buyer guidance or artwork presentation")
    for script_src in parser.local_scripts:
        parsed = urlparse(script_src)
        if parsed.scheme or script_src.startswith("//"):
            continue
        target = (path.parent / script_src).resolve()
        if not target.is_file():
            fail(f"{path}: local script not found: {script_src}")

print(
    f"LANDING VALIDATION OK: {len(published)} published products, "
    f"{len(actual_paths)} matching pages; document structure, product identity, "
    "images, SEO, buyer guidance, and local scripts verified."
)
