# HALL OF GREATNESS Publishing

A self-contained digital publishing section within the HALL OF GREATNESS static storefront.

## Structure
- `index.html` — publishing homepage
- `books/index.html` — digital library
- `books/<slug>/index.html` — individual title pages
- `about/index.html` — publisher profile and editorial scope
- `rights/index.html` — general digital rights and licensing information
- `data/books.json` — publishing catalogue data
- `assets/` — isolated styles and catalogue rendering script

## Design and integration safeguards
- All files live under `/publishing/`; the existing gallery homepage, catalogue, landing pages, scripts, and workflows are not modified by this foundation.
- CSS and JavaScript are namespaced to this section and loaded only by publishing pages.
- Gumroad remains the checkout and digital-delivery provider. Prices and package details should be checked on each live product page.
- This is a distinct publishing imprint/brand within HALL OF GREATNESS, not a claim of a separately incorporated legal entity.

## Book data maintenance
Update `data/books.json` when an edition, summary, cover, or product destination is verified. Avoid adding page counts, ISBNs, publication dates, or formats unless confirmed from the actual edition files or product listing.
