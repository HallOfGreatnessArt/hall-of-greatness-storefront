#!/usr/bin/env python3
"""Generate missing HALL OF GREATNESS landing pages from the verified catalogue.

Existing hand-crafted landing pages are intentionally preserved.
"""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "catalog-data.json").read_text(encoding="utf-8"))
PRODUCTS = {p["permalink"]: p for p in CATALOG["products"] if p.get("published")}
USAGE = {
    "Humanity": "A meaningful focal point for homes, offices, educational spaces, galleries, and places where human stories matter.",
    "Heritage": "A distinctive addition to homes, private studies, offices, galleries, museums, hotels, and cultural spaces.",
    "Elegance": "A refined accent for living rooms, bedrooms, offices, boutique hotels, wellness spaces, and considered interiors.",
    "Global": "An expressive statement for homes, creative studios, offices, hospitality spaces, and interiors shaped by imagination.",
    "Collection": "A coordinated art collection for homes, offices, hotels, galleries, reception areas, and curated interiors.",
}

def esc(value):
    return html.escape(str(value or ""), quote=True)

def money(value):
    return f"${float(value):,.2f}"

def render(product):
    title = product["name"].strip()
    summary = product["summary"].strip()
    cover = product["cover_url"].strip()
    url = product["url"].strip()
    slug = product["landing_slug"].strip()
    category = product.get("category", "Digital Art")
    is_bundle = bool(product.get("is_bundle"))
    canonical = f"https://hallofgreatnessart.github.io/hall-of-greatness-storefront/landing/{slug}/"
    contents = product.get("bundle_contents", [])
    items = []
    for permalink in contents:
        item = PRODUCTS.get(permalink)
        if item:
            items.append(f'<li><a href="../{esc(item["landing_slug"])}/">{esc(item["name"].strip())}</a></li>')
    contents_html = ""
    if is_bundle:
        contents_html = f"""
<section class="section">
  <div class="eyebrow">Inside this collection</div>
  <h2>One collection. Many stories.</h2>
  <p>Explore the individual artworks included in this curated collection. Each piece has its own character, while together they create a richer visual journey.</p>
  <ul class="contents">{''.join(items)}</ul>
</section>"""
    subtitle = "A curated collection of meaningful digital artworks" if is_bundle else "An original digital artwork from HALL OF GREATNESS"
    digital_note = "This is a digital product. No physical artwork or frame will be shipped. After purchase, Gumroad provides access to the files included with this product. Please review the supplied file specifications and license before printing or using the artwork."
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{esc(summary[:250])}">
<meta name="theme-color" content="#11110f">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="product"><meta property="og:title" content="{esc(title)} | HALL OF GREATNESS">
<meta property="og:description" content="{esc(summary[:250])}"><meta property="og:image" content="{esc(cover)}">
<meta property="product:price:amount" content="{float(product["price_usd"]):.2f}"><meta property="product:price:currency" content="USD">
<title>{esc(title)} | HALL OF GREATNESS</title>
<style>
:root{{--bg:#11110f;--panel:#1d1a15;--ink:#f5efe3;--muted:#c0b5a2;--gold:#dfbd75;--line:#493d2b}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(ellipse at 50% -15%,#554222 0,transparent 48%),var(--bg);color:var(--ink);font:16px/1.7 Arial,sans-serif}}
.wrap{{width:min(1080px,92%);margin:auto}}header{{padding:22px 0;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}}
.brand{{font:17px Georgia;letter-spacing:3px;color:var(--ink);text-decoration:none}}.brand span,footer strong{{color:var(--gold)}}header a.back{{color:var(--muted);font-size:12px;text-decoration:none}}
.hero{{display:grid;grid-template-columns:1.05fr .95fr;gap:42px;align-items:center;padding:64px 0}}.eyebrow{{color:var(--gold);font-size:10px;letter-spacing:4px;text-transform:uppercase}}
.hero h1{{font:clamp(38px,5vw,64px)/1.08 Georgia;margin:18px 0}}.sub{{font:italic 21px/1.5 Georgia;color:#efd99e}}.desc{{color:var(--muted);font:18px/1.85 Georgia}}
.art{{border:1px solid var(--line);padding:10px;background:var(--panel);box-shadow:0 22px 70px #0008}}.art img{{width:100%;display:block;max-height:650px;object-fit:contain}}
.price{{font:28px Georgia;color:var(--gold);margin:18px 0}}.btn{{display:inline-block;padding:15px 23px;background:var(--gold);color:#17140e;text-decoration:none;text-transform:uppercase;letter-spacing:1.2px;font-size:11px;font-weight:bold}}
.note{{font-size:12px;color:var(--muted);margin-top:12px}}.section{{padding:42px 0;border-top:1px solid var(--line)}}.section h2{{font:34px Georgia;font-weight:400;margin:8px 0 16px}}.section p{{max-width:820px;color:var(--muted);font:18px/1.85 Georgia}}
.contents{{columns:2;max-width:850px;padding-left:22px;color:var(--muted)}}.contents li{{padding:5px 0;break-inside:avoid}}.contents a{{color:#efd99e;text-decoration:none}}.closing{{text-align:center;padding:54px 12px 68px}}.closing h2{{font:clamp(30px,4vw,46px) Georgia;font-weight:400}}.closing p{{color:var(--muted);font:18px Georgia;max-width:650px;margin:0 auto 24px}}
footer{{padding:24px 0;border-top:1px solid var(--line);display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;color:var(--muted);font-size:12px}}
@media(max-width:760px){{.hero{{grid-template-columns:1fr;gap:24px;padding:42px 0}}.art{{max-width:620px;margin:auto}}.hero h1{{font-size:44px}}.sub{{font-size:19px}}.contents{{columns:1}}}}
</style></head>
<body><div class="wrap">
<header><a class="brand" href="../../index.html">HALL OF <span>GREATNESS</span></a><a class="back" href="../../index.html">← Return to the gallery</a></header>
<main>
<section class="hero"><div><div class="eyebrow">{esc(category)} · HALL OF GREATNESS</div><h1>{esc(title)}</h1><div class="sub">{esc(subtitle)}</div><p class="desc">{esc(summary)}</p>
<div class="price">{money(product["price_usd"])} <span style="font:12px Arial;color:var(--muted)">· Digital download</span></div>
<a class="btn" href="{esc(url)}" target="_blank" rel="noopener noreferrer">Explore &amp; Get the Artwork ↗</a><p class="note">Secure checkout and digital delivery on Gumroad.</p></div>
<div class="art"><img src="{esc(cover)}" alt="{esc(title)} digital artwork" loading="eager" fetchpriority="high"></div></section>
<section class="section"><div class="eyebrow">The meaning behind the artwork</div><h2>More than decoration. A feeling that stays.</h2><p>{esc(summary)}</p><p>Created for people who want their surroundings to reflect a story, a memory, a value, or a sense of beauty. Let this work become part of the atmosphere you create and the feeling you want your space to hold.</p></section>
{contents_html}
<section class="section"><div class="eyebrow">Where it belongs</div><h2>Art that finds its place</h2><p>{esc(USAGE.get(category, USAGE["Global"]))}</p></section>
<section class="section"><div class="eyebrow">Before you purchase</div><h2>Digital download details</h2><p>{esc(digital_note)}</p></section>
<section class="closing"><h2>Let your space tell a story.</h2><p>Choose art that reflects what you value—and let its meaning live with you.</p><a class="btn" href="{esc(url)}" target="_blank" rel="noopener noreferrer">Get {esc(title)} ↗</a></section>
</main>
<footer><span><strong>HALL OF GREATNESS</strong><br>Art with a Soul. A Message Without Borders.</span><span>Digital artwork · Instant download through Gumroad</span></footer>
</div></body></html>'''

created = 0
for product in CATALOG["products"]:
    if not product.get("published"):
        continue
    for field in ("landing_slug", "cover_url", "summary", "url", "permalink"):
        if not product.get(field):
            raise SystemExit(f'Missing {field} for {product.get("name")}')
    target = ROOT / "landing" / product["landing_slug"] / "index.html"
    if target.exists():
        continue
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(product), encoding="utf-8")
    created += 1
print(f"Generated {created} new landing pages; existing custom pages were preserved.")
