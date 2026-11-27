#!/usr/bin/env python3
"""Prepare Gumroad-native landing pages for newly published, eligible products only."""
from __future__ import annotations
import html, json, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CATALOG=json.loads((ROOT/"catalog-data.json").read_text(encoding="utf-8"))
MANIFEST_PATH=ROOT/"gumroad-landings/automation-manifest.json"
manifest=json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
known=set(manifest.get("existing_products",[]))|set(manifest.get("automatically_published_products",[]))
valid_types={"art-decor","ebook","course"}
pending=[]
skipped=[]

def esc(value):
    return html.escape(str(value or "").strip(), quote=True)

def slug(value):
    return re.sub(r"[^a-z0-9]+","-",str(value).lower()).strip("-") or "product"

def render(p):
    title=esc(p["name"])
    summary=esc(p["summary"])
    permalink=esc(p["permalink"])
    cover=esc(p["cover_url"])
    kind=p["content_type"]
    label={"art-decor":"DIGITAL ARTWORK","ebook":"DIGITAL BOOK","course":"DIGITAL COURSE"}[kind]
    hero={"art-decor":"A meaningful artwork for spaces with a story.","ebook":"Ideas and insight for a changing world.","course":"A learning experience designed to build practical understanding."}[kind]
    story={"art-decor":"Bring a story, a value, or a feeling into the spaces you inhabit.","ebook":"Explore the ideas, evidence, and perspectives presented in this digital publication.","course":"Explore the learning experience and the knowledge it is designed to share."}[kind]
    deliver={"art-decor":"Instant digital delivery after purchase. No physical print or frame will be shipped.","ebook":"Digital book delivery through Gumroad after purchase. No physical book will be shipped.","course":"Digital course access is provided according to the product details on Gumroad."}[kind]
    return f"""<!doctype html>
<html lang="en" data-theme="auto">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{summary[:250]}">
<title>{title} | HALL OF GREATNESS</title>
<style>
:root{{color-scheme:light dark;--bg:#f5f0e8;--surface:#fffaf2;--ink:#29241e;--muted:#74695b;--gold:#98733b;--line:#dfd3bf}}
@media(prefers-color-scheme:dark){{:root{{--bg:#141310;--surface:#201d18;--ink:#f5eee2;--muted:#c2b6a3;--gold:#dfbd78;--line:#4b4030}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 Georgia,serif}}
.shell{{width:min(1100px,calc(100% - 36px));margin:auto}}header,footer{{display:flex;justify-content:space-between;gap:16px;align-items:center;padding:22px 0;border-bottom:1px solid var(--line);flex-wrap:wrap}}
.brand{{font:600 13px Arial,sans-serif;letter-spacing:.2em;text-decoration:none}}.brand span{{color:var(--gold)}}
.kicker{{font:11px Arial,sans-serif;letter-spacing:.22em;text-transform:uppercase;color:var(--gold)}}
.hero{{display:grid;grid-template-columns:1fr 1fr;gap:clamp(24px,6vw,72px);align-items:center;padding:clamp(40px,8vw,88px) 0}}
h1{{font-size:clamp(38px,5.5vw,68px);line-height:1.06;font-weight:400;margin:16px 0;overflow-wrap:anywhere}}
.subtitle{{font-size:clamp(18px,2.2vw,24px);font-style:italic;color:var(--gold)}}
.copy{{font-size:18px;line-height:1.85;color:var(--muted)}}
.price{{font:32px Arial,sans-serif;color:var(--gold);margin:22px 0}}
.buy{{display:inline-flex;align-items:center;justify-content:center;min-height:52px;padding:14px 28px;background:var(--gold);color:#17130d;text-decoration:none;font:700 12px Arial,sans-serif;letter-spacing:.12em;text-transform:uppercase;border:1px solid var(--gold)}}
.art-wrap{{padding:14px;background:var(--surface);border:1px solid var(--line)}}.art{{display:block;width:100%;height:auto;max-height:680px;object-fit:contain}}
.section{{border-top:1px solid var(--line);padding:42px 0}}h2{{font-size:clamp(28px,4vw,42px);font-weight:400;margin:8px 0 18px}}
.note{{font:12px/1.7 Arial,sans-serif;color:var(--muted);margin-top:14px}}
.purchase{{text-align:center;padding:50px 0 66px;border-top:1px solid var(--line)}}.purchase .copy{{max-width:700px;margin:14px auto 20px}}
footer{{border-top:1px solid var(--line);border-bottom:0;color:var(--muted);font:11px Arial,sans-serif}}
a:focus-visible{{outline:3px solid var(--gold);outline-offset:4px}}
@media(max-width:720px){{.hero{{grid-template-columns:1fr;padding:36px 0;gap:22px}}.art-wrap{{grid-row:1}}.copy{{font-size:16px}}.buy{{width:100%}}header{{padding:16px 0}}footer{{flex-direction:column}}}}
@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important;transition:none!important}}}}
</style>
</head>
<body><div class="shell">
<header><a class="brand" href="https://alshayebemad.gumroad.com/">HALL OF <span>GREATNESS</span></a><span class="kicker">Art with a soul · A message without borders</span></header>
<main>
<section class="hero">
<div class="hero-copy">
<div class="kicker">{label} · HALL OF GREATNESS</div>
<h1 data-gumroad-field="name">{title}</h1>
<div class="subtitle">{esc(hero)}</div>
<p class="copy" data-gumroad-field="description">{summary}</p>
<div class="price" data-gumroad-field="price"></div>
<a class="buy" href="#" data-gumroad-action="buy">Get this digital product</a>
<p class="note">{esc(deliver)}</p>
</div>
<div class="art-wrap"><img class="art" src="{cover}" alt="{title} cover" loading="eager"></div>
</section>
<section class="section"><div class="kicker">THE STORY</div><h2>More than a product. An idea worth keeping.</h2><p class="copy">{esc(story)}</p><p class="copy">{summary}</p></section>
<section class="section"><div class="kicker">DIGITAL DELIVERY</div><h2>Ready when you are.</h2><p class="copy">{esc(deliver)} Please review the product details and included usage terms before purchase.</p></section>
<section class="purchase"><div class="kicker">DISCOVER HALL OF GREATNESS</div><h2>Make room for something meaningful.</h2><p class="copy">{summary}</p><div class="price" data-gumroad-field="price"></div><a class="buy" href="#" data-gumroad-action="buy">Get this digital product</a><div class="note" data-gumroad-field="rating"></div><div class="note" data-gumroad-field="review-count"></div></section>
</main>
<footer><span>HALL OF GREATNESS</span><span>Art with a Soul. A Message Without Borders.</span></footer>
</div></body></html>
"""

for p in CATALOG.get("products",[]):
    key=str(p.get("permalink","")).strip()
    if not p.get("published") or not key or key in known:
        continue
    reasons=[]
    if p.get("content_type") not in valid_types: reasons.append("missing or unsupported content_type")
    if p.get("pay_what_you_want") is not False: reasons.append("pay-what-you-want status is not verified as fixed-price")
    if not p.get("name") or not p.get("summary") or not p.get("cover_url","").startswith("https://"): reasons.append("missing product name, summary, or HTTPS cover")
    if not p.get("url","").startswith("https://"): reasons.append("missing HTTPS Gumroad product URL")
    if p.get("currency","usd").lower()!="usd": reasons.append("unsupported currency")
    if reasons:
        skipped.append({"permalink":key,"name":p.get("name"),"reasons":reasons})
        continue
    target=ROOT/"gumroad-landings"/slug(p.get("landing_slug") or p["name"])/"landing.html"
    if target.exists():
        existing_html=target.read_text(encoding="utf-8")
        if 'data-gumroad-action="buy"' not in existing_html:
            skipped.append({"permalink":key,"name":p.get("name"),"reasons":["existing landing file lacks a Gumroad buy action; manual review required"]})
            continue
    else:
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(render(p),encoding="utf-8")
    pending.append({"permalink":key,"name":p["name"],"landing_file":str(target.relative_to(ROOT)),"content_type":p["content_type"]})

report={"pending":pending,"skipped":skipped}
(ROOT/"gumroad-landings"/"automation-pending.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"pending_count":len(pending),"skipped_count":len(skipped),"pending":pending,"skipped":skipped},ensure_ascii=False))
