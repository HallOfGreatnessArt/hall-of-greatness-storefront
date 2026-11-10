# HALL OF GREATNESS — Digital Art Gallery

A mobile-first, responsive storefront for the HALL OF GREATNESS digital art catalogue.

## Contents
- `index.html` — dark-and-gold gallery with featured works, live product covers, collections, search, and category filters.
- `catalog-data.json` — catalogue snapshot of 34 product records: 30 individual artworks and 4 bundles; public Gumroad visibility must be checked separately. Unpublished drafts are excluded.
- `landing/` — individual product and collection landing pages.
- `scripts/generate_landing_pages.py` — creates missing landing pages from the verified catalogue while preserving existing hand-crafted pages.
- `.github/workflows/publish-storefront.yml` — scheduled (every 15 minutes) and manually triggered catalogue sync, page generation, validation, and GitHub Pages deployment.
- `scripts/sync_gumroad_catalog.py` — read-only Gumroad product sync that appends newly published products only; existing catalogue entries are not rewritten.

## Product and account integrity
The storefront is a presentation layer. It links to existing Gumroad product pages and does not change product names, prices, files, covers, bundle contents, or publication settings. The catalogue includes only published products from the connected Emad Alshayeb creator account.

## Landing-page generation
The generator uses each product's verified public Gumroad cover, current selling URL, listed price, product summary, and (for bundles) the exact included-product list returned by Gumroad. Existing custom landing pages are preserved. All other published products receive a responsive page using the shared dark-and-gold design.

## Automatic Gumroad sync
1. Create a Gumroad personal access token for the **Emad Alshayeb** account with permission to read products.
2. In this repository, open Settings → Secrets and variables → Actions → New repository secret.
3. Set the secret name to `GUMROAD_ACCESS_TOKEN` and paste the token as its value. Never commit the token to a file.
4. The scheduled workflow checks Gumroad every 15 minutes. It appends newly published products only; unpublished drafts are ignored. Existing catalogue records, prices, product URLs, and landing-page slugs are left unchanged.
5. New bundles are added only when their included-product list is available to verify. Products missing a usable public cover or description are skipped with a warning rather than creating a broken landing page.

Without the repository secret, scheduled runs safely skip the Gumroad API sync and only rebuild the existing storefront. GitHub Actions may delay scheduled runs during high load.

## Publish and test
1. In repository Settings → Pages, set the build and deployment source to **GitHub Actions**.
2. Add `GUMROAD_ACCESS_TOKEN` as described above.
3. Open Actions → **Publish HALL OF GREATNESS storefront** and run it manually for the first test.
4. Confirm both the sync and deployment jobs complete successfully before considering a newly discovered product published on the storefront.
