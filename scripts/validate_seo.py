#!/usr/bin/env python3
"""Validate homepage/landing HTML SEO structure and the generated XML sitemap."""
import json
from html.parser import HTMLParser
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://hallofgreatnessart.github.io/hall-of-greatness-storefront/"
catalog = json.loads((ROOT / "catalog-data.json").read_text(encoding="utf-8"))
published = [p for p in catalog["products"] if p.get("published") and p.get("landing_slug")]

class SEOParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = []
        self.title_depth = 0
        self.title_text = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == "meta":
            self.meta.append(dict(attrs))
        elif tag.lower() == "title":
            self.title_depth += 1
    def handle_endtag(self, tag):
        if tag.lower() == "title" and self.title_depth:
            self.title_depth -= 1
    def handle_data(self, data):
        if self.title_depth:
            self.title_text.append(data)

def validate_html(path, expected_canonical, homepage=False):
    source = path.read_text(encoding="utf-8")
    assert source.lower().count("<head>") == 1, f"{path}: expected one opening head tag"
    assert source.lower().count("</head>") == 1, f"{path}: expected one closing head tag"
    parser = SEOParser()
    parser.feed(source)
    assert parser.title_text and "".join(parser.title_text).strip(), f"{path}: missing title"
    meta = parser.meta
    assert any(m.get("name", "").lower() == "description" and m.get("content", "").strip() for m in meta), f"{path}: missing meta description"
    assert any(m.get("name", "").lower() == "robots" and "noindex" in m.get("content", "").lower() for m in meta) is False, f"{path}: unexpected noindex"
    assert f'<link rel="canonical" href="{expected_canonical}">' in source, f"{path}: canonical mismatch"
    if homepage:
        for marker in ('property="og:title"', 'property="og:description"', 'name="twitter:card"'):
            assert marker in source, f"{path}: missing {marker}"
        assert 'name="google-site-verification"' in source, f"{path}: verification meta missing"
    else:
        assert 'property="og:title"' in source and 'property="og:description"' in source, f"{path}: missing Open Graph metadata"
    return source

home_path = ROOT / "index.html"
validate_html(home_path, BASE, homepage=True)
for product in published:
    slug = product["landing_slug"].strip("/")
    path = ROOT / "landing" / slug / "index.html"
    assert path.is_file(), f"Missing landing page: {path}"
    validate_html(path, BASE + "landing/" + slug + "/")

robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
assert "User-agent: *" in robots and "Allow: /" in robots
assert "Sitemap: " + BASE + "sitemap.xml" in robots

sitemap_path = ROOT / "sitemap.xml"
root = ET.parse(sitemap_path).getroot()
sm = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
      "image": "http://www.google.com/schemas/sitemap-image/1.1"}
assert root.tag == "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset"
locs = [node.text for node in root.findall("sm:url/sm:loc", sm)]
expected = {BASE, BASE + "privacy.html", BASE + "terms.html", BASE + "contact.html"}
expected.update(BASE + "landing/" + p["landing_slug"].strip("/") + "/" for p in published)
assert len(locs) == len(set(locs)), "Duplicate sitemap URLs"
assert set(locs) == expected, f"Sitemap mismatch: expected {len(expected)} URLs, got {len(locs)}"
image_entries = root.findall("sm:url/image:image", sm)
assert len(image_entries) == len(published), f"Expected {len(published)} image entries, got {len(image_entries)}"

print(f"SEO validation passed: homepage + {len(published)} landing pages.")
print(f"robots.txt passed; sitemap XML valid with {len(locs)} URLs and {len(image_entries)} image entries.")
