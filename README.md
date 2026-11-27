# HALL OF GREATNESS — Digital Storefront

HALL OF GREATNESS is the umbrella creative brand with three distinct destinations: Art & Decor, HALL OF GREATNESS Publishing, and Educational Courses.

## Structure
- `index.html` — main storefront and navigation to three separate destinations.
- `#art-decor` — printable art and decor products only (`content_type: art-decor`).
- `#ebooks` — digital books with a direct route to the dedicated Publishing Library.
- `#courses` — educational courses only (`content_type: course`).
- `publishing/` — dedicated publishing identity, editorial library, individual book pages, About, and Rights.
- `publishing/data/books.json` — editorial catalogue of five individual books and the five-book collection.
- `publishing/assets/` — publishing-specific presentation and bilingual interface.
- `catalog-data.json` — current product catalogue snapshot; count changes as the catalogue is reconciled.
- `landing/` — individual product landing pages.
- `scripts/refresh_ebook_landing_pages.py` — preview-only Gumroad e-book page refresh; it does not publish pages or change live products.

## Separation and product integrity
The homepage renders products by explicit `content_type`: `art-decor`, `ebook`, or `course`. Publishing is a distinct editorial imprint within HALL OF GREATNESS, not a claim that a separate legal company has been incorporated. Its navigation returns readers to the Publishing Library rather than the general Gumroad account homepage.

Repository changes do not change Gumroad product names, prices, files, covers, bundle contents, or publication states. Payment and digital delivery remain on the relevant Gumroad product page.

## Deployment
The existing GitHub Actions workflow controls catalogue validation, page generation, sitemap checks, and GitHub Pages deployment. Do not dispatch a publishing workflow merely to preview changes. Gumroad credentials must remain in GitHub Actions secrets and must never be committed.
