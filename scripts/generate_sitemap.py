#!/usr/bin/env python3
"""Generate the storefront URL sitemap and a Google-compatible artwork image sitemap."""
import json
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://hallofgreatnessart.github.io/hall-of-greatness-storefront/"
CATALOG = json.loads((ROOT / "catalog-data.json").read_text(encoding="utf-8"))
PUBLISHED = [
    product for product in CATALOG["products"]
    if product.get("published") and product.get("landing_slug")
]
URLS = [BASE, BASE + "privacy.html", BASE + "terms.html", BASE + "contact.html"]

lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
    'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
]
for url in URLS:
    lines.append(f"  <url><loc>{escape(url)}</loc></url>")

for product in PUBLISHED:
    page_url = BASE + "landing/" + product["landing_slug"].strip("/") + "/"
    image_url = escape(product["cover_url"])
    image_title = escape(product["name"].strip())
    image_caption = escape(product.get("summary", "").strip())
    lines.extend([
        "  <url>",
        f"    <loc>{escape(page_url)}</loc>",
        "    <image:image>",
        f"      <image:loc>{image_url}</image:loc>",
        f"      <image:title>{image_title}</image:title>",
    ])
    if image_caption:
        lines.append(f"      <image:caption>{image_caption}</image:caption>")
    lines.extend(["    </image:image>", "  </url>"])

lines.append("</urlset>")
(ROOT / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
(ROOT / "robots.txt").write_text(
    "User-agent: *\nAllow: /\nSitemap: " + BASE + "sitemap.xml\n",
    encoding="utf-8",
)
print(
    f"Generated {len(URLS) + len(PUBLISHED)} sitemap URLs "
    f"with {len(PUBLISHED)} artwork image entries."
)
