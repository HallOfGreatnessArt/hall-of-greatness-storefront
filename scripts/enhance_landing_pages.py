#!/usr/bin/env python3
"""Apply consistent buyer-focused details to every published landing page.

This runs after page generation and is deliberately idempotent. It preserves
product-specific copy, covers, prices, canonical URLs, and Gumroad links.
"""
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
@media(max-width:760px){.purchase-strip,.print-panel{grid-template-columns:1fr;gap:8px}.purchase-chip{text-align:left}.print-step{padding:15px}}
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

for path in sorted((ROOT / "landing").glob("*/index.html")):
    page = path.read_text(encoding="utf-8")
    if "id=\"printing\"" in page:
        continue
    if "</style>" not in page:
        raise SystemExit(f"Missing style block: {path}")
    page = page.replace("</style>", STYLE + "\n</style>", 1)
    if 'class="hero"' in page:
        start = page.find('<section class="hero"')
        end = page.find("</section>", start)
        if end < 0:
            raise SystemExit(f"Could not locate hero section end: {path}")
        end += len("</section>")
        page = page[:end] + "\n" + STRIP + page[end:]
    else:
        raise SystemExit(f"Missing hero section: {path}")
    if '<section class="closing"' in page:
        page = page.replace('<section class="closing"', DETAILS + '\n<section class="closing"', 1)
    else:
        raise SystemExit(f"Missing closing CTA section: {path}")
    path.write_text(page, encoding="utf-8")
print(f"Enhanced {len(list((ROOT / 'landing').glob('*/index.html')))} landing pages with digital-purchase clarity and practical print guidance.")
