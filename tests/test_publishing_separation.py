#!/usr/bin/env python3
"""Read-only integrity checks for the dedicated HALL OF GREATNESS Publishing section."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
catalog = json.loads((ROOT / "catalog-data.json").read_text(encoding="utf-8"))
publishing = json.loads((ROOT / "publishing/data/books.json").read_text(encoding="utf-8"))
published = {p["permalink"]: p for p in catalog["products"] if p.get("published") is True}
ebooks = {k: p for k, p in published.items() if p.get("content_type") == "ebook"}
art = {k: p for k, p in published.items() if p.get("content_type") == "art-decor"}
books = publishing["books"]
ids = {b.get("permalink") for b in books}
assert len(ebooks) == 6, f"Expected six published e-book products, found {len(ebooks)}"
assert ids == set(ebooks), f"Publishing catalogue mismatch: missing={set(ebooks)-ids}, extra={ids-set(ebooks)}"
assert not ids.intersection(art), "Art/decor product leaked into Publishing"
for book in books:
    product = ebooks[book["permalink"]]
    assert book["url"] == product["url"], f"Wrong purchase URL for {book['slug']}"
    assert book["cover"] == product["cover_url"], f"Wrong cover for {book['slug']}"
    page = ROOT / "publishing" / "books" / book["slug"] / "index.html"
    assert page.is_file(), f"Missing detail page: {page.relative_to(ROOT)}"
refresh = (ROOT / "scripts/refresh_ebook_landing_pages.py").read_text(encoding="utf-8")
assert 'code==="ar"?"العربية":"English"' in refresh, "Arabic language metadata label is incorrect"
assert 'href="https://hallofgreatnessart.github.io/hall-of-greatness-storefront/publishing/"' in refresh, "E-book brand link must return to Publishing"
assert 'href="https://alshayebemad.gumroad.com/"' not in refresh, "E-book page still links its brand to the general Gumroad homepage"
print("PASS: six e-book products, matching URLs/covers, six Publishing detail pages, no art/decor leakage, correct Arabic language label.")
