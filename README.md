# HALL OF GREATNESS — Digital Art Gallery

A mobile-first, responsive storefront for the HALL OF GREATNESS digital art catalogue.

## Contents
- `index.html` — dark-and-gold gallery with featured works, live product covers, collections, search, and category filters.
- `catalog-data.json` — verified snapshot of 33 published Gumroad products: 29 individual artworks and 4 bundles. Unpublished drafts are excluded.
- `landing/` — individual product and collection landing pages.
- `scripts/generate_landing_pages.py` — creates missing landing pages from the verified catalogue while preserving existing hand-crafted pages.
- `.github/workflows/publish-storefront.yml` — manually triggered GitHub Pages build, page generation, and validation.

## Product and account integrity
The storefront is a presentation layer. It links to existing Gumroad product pages and does not change product names, prices, files, covers, bundle contents, or publication settings. The catalogue includes only published products from the connected Emad Alshayeb creator account.

## Landing-page generation
The generator uses each product's verified public Gumroad cover, current selling URL, listed price, product summary, and (for bundles) the exact included-product list returned by Gumroad. Existing custom landing pages are preserved. All other published products receive a responsive page using the shared dark-and-gold design.

## Publish
1. In repository Settings → Pages, set the build and deployment source to **GitHub Actions**.
2. Open Actions → **Publish HALL OF GREATNESS storefront**.
3. Run the workflow after reviewing the changes.

The workflow is manual (`workflow_dispatch`). It generates and validates all 33 pages before deployment. A successful GitHub Actions run is required before considering changes published.
