#!/usr/bin/env python3
"""Apply buyer guidance and a clean, proportion-preserving artwork display to landing pages.

The catalogue cover is never cropped, stretched, or duplicated as two different mockups.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STYLE = """
/* Buyer clarity and print guidance */
.purchase-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:-12px 0 38px}
.purchase-chip{border:1px solid var(--line);background:var(--panel);padding:13px 15px;text-align:center;color:#e8ddca;font-size:12px;letter-spacing:.3px}
.purchase-chip strong{display:block;color:var(--gold);font:16px Georgia;margin-bottom:3px}
.print-panel{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:22px 0 8px}
.print-step{border:1px solid var(--line);background:var(--panel);padding:18px}
.print-step b{display:block;color:var(--gold);font:18px Georgia;margin-bottom:7px}
.print-step p{font:14px/1.7 Arial,sans-serif!important;margin:0;color:var(--muted)}
.digital-reminder{font-size:13px!important;border-left:2px solid var(--gold);padding:10px 16px;background:#1d1a15}

/* Clean artwork display: retain the image's native aspect ratio and avoid black letterboxing */
.room-showcase{padding:42px 0 54px;border-top:1px solid var(--line)}
.room-showcase .room-intro{text-align:center;max-width:720px;margin:0 auto 24px}
.room-showcase h2{font:34px Georgia;font-weight:400;margin:8px 0 12px}
.room-showcase .room-intro p{color:var(--muted);font:16px/1.7 Georgia}
.artwork-display{min-height:300px;display:flex;align-items:center;justify-content:center;padding:28px 18px;background:radial-gradient(ellipse at 50% 35%,#e6d9c2 0%,#c8b89d 58%,#8d7b62 100%);border:1px solid #8b7552;box-shadow:inset 0 0 55px #38281722}
.artwork-frame{display:inline-flex;align-items:center;justify-content:center;max-width:92%;padding:12px;background:linear-gradient(135deg,#fff1d3,#9a7139 24%,#f1dfb9 48%,#75512c 75%,#e6c88f);box-shadow:0 16px 34px #24190d70,0 2px 5px #fff9 inset}
.room-artwork{display:block;width:auto;height:auto;max-width:min(100%,520px);max-height:440px;object-fit:contain;background:transparent;box-shadow:0 0 0 1px #6f5735}
@media(max-width:760px){
 .purchase-strip,.print-panel{grid-template-columns:1fr;gap:8px}
 .purchase-chip{text-align:left}.print-step{padding:15px}
 .artwork-display{min-height:240px;padding:18px 10px}
 .artwork-frame{max-width:96%;padding:8px}
 .room-artwork{max-width:100%;max-height:360px}
 .room-showcase h2{font-size:29px}
}

/* Consistent mobile usability */
html{scroll-padding-top:16px;-webkit-text-size-adjust:100%}
body{min-width:320px;overflow-x:hidden}
img{max-width:100%;height:auto}
a:focus-visible,.btn:focus-visible{outline:3px solid var(--gold);outline-offset:3px}
header a.back,.btn{min-height:44px;display:inline-flex;align-items:center;justify-content:center}
@media(max-width:760px){
 .wrap{width:calc(100% - 32px)}
 header{padding:16px 0;gap:10px}
 .brand{font-size:15px;letter-spacing:2px}
 header a.back{font-size:12px;padding:8px 0}
 .hero{padding:32px 0;gap:22px}
 .hero h1{font-size:clamp(34px,8vw,44px);line-height:1.12;overflow-wrap:anywhere}
 .eyebrow{font-size:10px;letter-spacing:2px;line-height:1.5}
 .desc,.section p{font-size:16px;line-height:1.75}
 .art{width:100%;padding:7px}
 .art img{width:100%;height:auto;max-height:none;object-fit:contain}
 .btn{width:100%;text-align:center;padding:14px 16px;line-height:1.45}
 .section{padding:30px 0}
 .section h2,.room-showcase h2{font-size:clamp(25px,6vw,30px);line-height:1.2}
 .purchase-strip,.print-panel{grid-template-columns:1fr}
 .purchase-chip{text-align:left}
 .artwork-display{min-height:0;padding:18px 10px}
 .artwork-frame{max-width:100%;padding:6px}
 .room-artwork{max-width:100%;max-height:60vh;width:auto}
 .closing{padding:38px 10px 48px}
 .closing p{font-size:16px;line-height:1.65}
 footer{font-size:11px;line-height:1.6}
}

"""

STRIP = """
<div class="purchase-strip" aria-label="Digital product information">
  <div class="purchase-chip"><strong>Digital download</strong>Access your files after checkout</div>
  <div class="purchase-chip"><strong>Print your way</strong>Choose a size suited to your space</div>
  <div class="purchase-chip"><strong>Made to display</strong>For homes, studios, and meaningful spaces</div>
</div>
"""

DETAILS = """
<section class="section" id="printing">
  <div class="eyebrow">From download to display</div>
  <h2>Make the artwork part of your space</h2>
  <div class="print-panel">
    <div class="print-step"><b>01 · Purchase</b><p>Complete your secure checkout on Gumroad. Your purchase is for a digital product.</p></div>
    <div class="print-step"><b>02 · Download</b><p>Access the files supplied with this product through Gumroad and review the included specifications.</p></div>
    <div class="print-step"><b>03 · Print</b><p>Choose a print size that preserves the artwork's original proportions. A local print professional can help match the dimensions to the supplied file.</p></div>
  </div>
  <p class="digital-reminder"><strong>Please note:</strong> No physical artwork or frame is shipped. Available file formats, resolution, proportions, and usage terms are those stated in the product download and included license.</p>
</section>
"""

def room_showcase(page, path):
    match = re.search(r'<div class="art">.*?<img\b[^>]*\bsrc="([^"]+)"[^>]*\balt="([^"]*)"', page, flags=re.S)
    if not match:
        raise SystemExit(f"Could not locate original artwork image: {path}")
    src, alt = match.group(1), match.group(2)
    section = f"""
<section class="room-showcase" id="room-showcase">
  <div class="room-intro">
    <div class="eyebrow">Artwork presentation</div>
    <h2>Imagine it in a refined frame</h2>
    <p>A second presentation helps you picture the artwork as a framed display, while preserving its original proportions.</p>
  </div>
  <div class="artwork-display">
    <div class="artwork-frame"><img class="room-artwork" src="{src}" alt="{alt} shown in a refined frame" loading="lazy"></div>
  </div>
</section>
"""
    pattern = r'<section class="room-showcase" id="room-showcase">.*?</section>'
    if re.search(pattern, page, flags=re.S):
        return re.sub(pattern, lambda _: section.strip(), page, count=1, flags=re.S)
    marker = '<div class="purchase-strip"'
    if marker in page:
        pos = page.find(marker)
        return page[:pos] + section + "\n" + page[pos:]
    marker = '<section class="section" id="printing">'
    if marker in page:
        pos = page.find(marker)
        return page[:pos] + section + "\n" + page[pos:]
    raise SystemExit(f"Could not find insertion point for artwork display: {path}")

pages = sorted((ROOT / "landing").glob("*/index.html"))
for path in pages:
    page = path.read_text(encoding="utf-8")
    if "</style>" in page:
        page = re.sub(r'/\* Buyer clarity and print guidance \*/.*?(?=</style>)', '', page, flags=re.S)
        page = page.replace("</style>", STYLE + "\n</style>", 1)
    if 'class="purchase-strip"' not in page:
        start = page.find('<section class="hero"')
        end = page.find("</section>", start)
        if start < 0 or end < 0:
            raise SystemExit(f"Missing hero section: {path}")
        page = page[:end + len("</section>")] + "\n" + STRIP + page[end + len("</section>"):]
    if 'id="printing"' not in page:
        if '<section class="closing"' not in page:
            raise SystemExit(f"Missing closing CTA section: {path}")
        page = page.replace('<section class="closing"', DETAILS + '\n<section class="closing"', 1)
    page = room_showcase(page, path)
    # Add consistent search/social metadata and trust links to every product landing page.
    social = """<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="HALL OF GREATNESS | Digital Art">
<meta name="twitter:description" content="Discover meaningful printable art from HALL OF GREATNESS.">
"""
    if 'name="twitter:card"' not in page:
        page = page.replace("</head>", social + "\n</head>", 1)
    if 'class="footer-links"' not in page:
        links = """<nav class="footer-links" aria-label="Information and support"><a href="../../privacy.html">Privacy</a><a href="../../terms.html">Terms</a><a href="../../contact.html">Contact</a><a href="https://alshayebemad.gumroad.com/" target="_blank" rel="noopener">Gumroad store ↗</a></nav>"""
        page = re.sub(r'(</footer>)', links + r'\n\1', page, count=1)
        page = page.replace("</style>", ".footer-links{display:flex;gap:16px;flex-wrap:wrap;align-items:center}.footer-links a{color:var(--gold);text-decoration:none;min-height:44px;display:inline-flex;align-items:center;font-size:12px}\n</style>", 1)
    path.write_text(page, encoding="utf-8")

print(f"Updated {len(pages)} landing pages: artwork proportions, buyer guidance, SEO metadata, and trust navigation.")


# Product-level search and social metadata. Values are sourced from the verified catalogue.
import html as html_lib
import json

catalog = json.loads((ROOT / "catalog-data.json").read_text(encoding="utf-8"))
products_by_slug = {
    str(product.get("landing_slug", "")).strip(): product
    for product in catalog.get("products", [])
    if product.get("published") and product.get("landing_slug")
}

def get_meta_value(page, attribute, key):
    pattern = re.compile(
        r'<meta\b(?=[^>]*\\b' + re.escape(attribute) +
        r'\s*=\s*["\\\']' + re.escape(key) + r'["\\\'])[^>]*>',
        flags=re.I,
    )
    match = pattern.search(page)
    if not match:
        return ""
    content = re.search(r'\bcontent\s*=\\s*(["\\\'])(.*?)\\1', match.group(0), flags=re.I | re.S)
    return html_lib.unescape(content.group(2)).strip() if content else ""

def set_meta_tag(page, attribute, key, value):
    pattern = re.compile(
        r'<meta\b(?=[^>]*\\b' + re.escape(attribute) +
        r'\s*=\s*["\\\']' + re.escape(key) + r'["\\\'])[^>]*>\\s*',
        flags=re.I,
    )
    page = pattern.sub("", page)
    tag = f'<meta {attribute}="{html_lib.escape(key, quote=True)}" content="{html_lib.escape(value, quote=True)}">\\n'
    return page.replace("</head>", tag + "</head>", 1)

for path in pages:
    page = path.read_text(encoding="utf-8")
    product = products_by_slug.get(path.parent.name)
    canonical_match = re.search(r'<link\b[^>]*\brel=["\\\']canonical["\\\'][^>]*\bhref=["\\\']([^"\\\']+)["\\\']', page, flags=re.I)
    canonical = html_lib.unescape(canonical_match.group(1)) if canonical_match else ""
    title_match = re.search(r'<title>(.*?)</title>', page, flags=re.I | re.S)
    page_title = html_lib.unescape(re.sub(r"\s+", " ", title_match.group(1))).strip() if title_match else "HALL OF GREATNESS | Digital Art"
    og_title = get_meta_value(page, "property", "og:title") or page_title
    description = get_meta_value(page, "name", "description")
    social_description = get_meta_value(page, "property", "og:description") or description
    image_url = get_meta_value(page, "property", "og:image")
    if product:
        image_url = image_url or str(product.get("cover_url", "")).strip()
        description = description or str(product.get("summary", "")).strip()
        social_description = social_description or description
    if canonical:
        page = set_meta_tag(page, "property", "og:url", canonical)
    if description:
        page = set_meta_tag(page, "name", "description", description)
        page = set_meta_tag(page, "property", "og:description", social_description or description)
    page = set_meta_tag(page, "name", "twitter:card", "summary_large_image")
    page = set_meta_tag(page, "name", "twitter:title", og_title)
    if social_description:
        page = set_meta_tag(page, "name", "twitter:description", social_description)
    if image_url:
        page = set_meta_tag(page, "name", "twitter:image", image_url)

    schema_pattern = re.compile(
        r'<script\b(?=[^>]*\\bid=["\\\']product-jsonld["\\\'])[^>]*>.*?</script>\s*',
        flags=re.I | re.S,
    )
    page = schema_pattern.sub("", page)
    if product:
        schema = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": str(product.get("name", "")).strip(),
            "description": str(product.get("summary", "")).strip() or description,
            "image": [str(product.get("cover_url", "")).strip()],
            "brand": {"@type": "Brand", "name": "HALL OF GREATNESS"},
            "category": str(product.get("category", "Digital Art")),
            "offers": {
                "@type": "Offer",
                "url": str(product.get("url", "")).strip(),
                "priceCurrency": "USD",
                "price": f'{float(product.get("price_usd", 0)):.2f}',
                "availability": "https://schema.org/InStock",
            },
        }
        schema_json = json.dumps(schema, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        page = page.replace(
            "</head>",
            '<script type="application/ld+json" id="product-jsonld">' + schema_json + '</script>\\n</head>',
            1,
        )
    path.write_text(page, encoding="utf-8")

print(f"SEO metadata and Product structured data refreshed for {len(pages)} landing pages.")
