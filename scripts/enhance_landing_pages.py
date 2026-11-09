#!/usr/bin/env python3
"""Apply buyer guidance and premium room mockups to every published landing page.

The mockup reuses each product's exact original cover image; it never regenerates
or alters the artwork. Safe to run repeatedly and preserves custom page content.
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

/* Premium interior mockups using the untouched original artwork image */
.room-showcase{padding:42px 0 54px;border-top:1px solid var(--line)}
.room-showcase .room-intro{text-align:center;max-width:720px;margin:0 auto 24px}
.room-showcase h2{font:34px Georgia;font-weight:400;margin:8px 0 12px}
.room-showcase .room-intro p{color:var(--muted);font:16px/1.7 Georgia}
.room-mockups{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.room-scene{position:relative;isolation:isolate;overflow:hidden;min-height:330px;aspect-ratio:4/3;border:1px solid #66543a;background:linear-gradient(180deg,#d7c5a5 0%,#c6ad88 72%,#6d5945 72%,#594633 100%)}
.room-scene.office{background:linear-gradient(180deg,#b7a68d 0%,#9e8b70 72%,#493b2d 72%,#30271f 100%)}
.room-scene:before{content:"";position:absolute;inset:0 0 28%;z-index:-1;background:repeating-linear-gradient(90deg,transparent 0 32%,#ffffff0b 32.2% 32.5%),linear-gradient(110deg,#ffffff25,transparent 55%)}
.room-scene:after{content:"";position:absolute;left:0;right:0;bottom:0;height:28%;z-index:-1;background:linear-gradient(180deg,#705b45,#342a22);box-shadow:0 -5px 16px #2a201633}
.room-window{position:absolute;left:5%;top:9%;width:17%;height:43%;border:8px solid #eee0c6;background:linear-gradient(145deg,#dce6e4,#a9bfc0 55%,#e8d9bd);box-shadow:0 5px 15px #0002}
.office .room-window{left:auto;right:5%;width:14%;height:38%;background:linear-gradient(145deg,#d8d9d2,#a7b2ad)}
.room-frame{position:absolute;left:50%;top:8%;transform:translateX(-50%);height:64%;width:39%;padding:12px;background:linear-gradient(135deg,#f7e8c8,#a47c3f 30%,#ead7ad 52%,#78562e 100%);box-shadow:0 13px 26px #24190d66,0 2px 5px #fff8 inset}
.room-frame:before{content:"";position:absolute;inset:6px;border:1px solid #72552e;pointer-events:none}
.room-artwork{display:block;width:100%;height:100%;object-fit:contain;background:#171512}
.room-sofa{position:absolute;left:13%;right:13%;bottom:0;height:27%;border-radius:28px 28px 0 0;background:linear-gradient(180deg,#b7a18a,#796653);box-shadow:0 -8px 15px #251b1430}
.room-sofa:before,.room-sofa:after{content:"";position:absolute;bottom:0;width:13%;height:82%;background:#8e7964;border-radius:12px 12px 0 0}
.room-sofa:before{left:-7%}.room-sofa:after{right:-7%}
.room-table{position:absolute;left:39%;bottom:8%;width:22%;height:8%;border-radius:50%;background:#493728;box-shadow:0 16px 0 -5px #30251c}
.office .room-sofa{left:8%;right:8%;height:14%;border-radius:3px;background:linear-gradient(180deg,#654f3c,#3d3025)}
.office .room-table{left:17%;width:66%;height:7%;bottom:13%;border-radius:3px;background:#533c2a;box-shadow:0 23px 0 -8px #2a2018}
.room-caption{position:absolute;left:0;right:0;bottom:8px;text-align:center;color:#fff4df;text-shadow:0 1px 3px #000;font:11px Arial;letter-spacing:2px;text-transform:uppercase}
@media(max-width:760px){
 .purchase-strip,.print-panel,.room-mockups{grid-template-columns:1fr;gap:8px}
 .purchase-chip{text-align:left}.print-step{padding:15px}
 .room-scene{min-height:270px}.room-showcase h2{font-size:29px}
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
    if 'id="room-showcase"' in page:
        return page
    match = re.search(r'<div class="art">\s*<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"[^>]*>', page)
    if not match:
        raise SystemExit(f"Could not locate original artwork image: {path}")
    src, alt = match.group(1), match.group(2)
    section = f"""
<section class="room-showcase" id="room-showcase">
  <div class="room-intro">
    <div class="eyebrow">See it in your space</div>
    <h2>Imagine the artwork on your wall</h2>
    <p>Two interior settings show how the original artwork can complement an elegant home or a refined workspace. The artwork itself is kept unchanged.</p>
  </div>
  <div class="room-mockups">
    <div class="room-scene living" role="img" aria-label="Living room presentation of {alt}">
      <div class="room-window"></div>
      <div class="room-frame"><img class="room-artwork" src="{src}" alt="{alt} displayed in a framed living room mockup" loading="lazy"></div>
      <div class="room-sofa"></div><div class="room-table"></div>
      <div class="room-caption">Elegant living room</div>
    </div>
    <div class="room-scene office" role="img" aria-label="Office presentation of {alt}">
      <div class="room-window"></div>
      <div class="room-frame"><img class="room-artwork" src="{src}" alt="{alt} displayed in a framed office mockup" loading="lazy"></div>
      <div class="room-sofa"></div><div class="room-table"></div>
      <div class="room-caption">Refined office</div>
    </div>
  </div>
</section>
"""
    marker = '<div class="purchase-strip"'
    if marker in page:
        pos = page.find(marker)
        return page[:pos] + section + "\n" + page[pos:]
    marker = '<section class="section" id="printing">'
    if marker in page:
        pos = page.find(marker)
        return page[:pos] + section + "\n" + page[pos:]
    raise SystemExit(f"Could not find insertion point for room mockup: {path}")

for path in sorted((ROOT / "landing").glob("*/index.html")):
    page = path.read_text(encoding="utf-8")
    if ".room-showcase{" not in page and "</style>" in page:
        page = page.replace("</style>", STYLE + "\n</style>", 1)
    if 'class="purchase-strip"' not in page:
        if 'class="hero"' not in page:
            raise SystemExit(f"Missing hero section: {path}")
        start = page.find('<section class="hero"')
        end = page.find("</section>", start)
        if end < 0:
            raise SystemExit(f"Could not locate hero end: {path}")
        page = page[:end + len("</section>")] + "\n" + STRIP + page[end + len("</section>"):]
    if 'id="printing"' not in page:
        if '<section class="closing"' not in page:
            raise SystemExit(f"Missing closing CTA section: {path}")
        page = page.replace('<section class="closing"', DETAILS + '\n<section class="closing"', 1)
    page = room_showcase(page, path)
    path.write_text(page, encoding="utf-8")

print(f"Enhanced {len(list((ROOT / 'landing').glob('*/index.html')))} landing pages with buyer guidance and two original-art interior mockups.")
