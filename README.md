# HALL OF GREATNESS — Digital Art Gallery

A mobile-first, responsive storefront for the HALL OF GREATNESS digital art catalogue.

## Contents
- `index.html` — dark-and-gold gallery with collection highlights, artwork search, category filters, and artist introduction.
- `catalog-data.json` — catalogue of 32 published Gumroad products: 4 bundles and 28 individual artworks.
- `.github/workflows/publish-storefront.yml` — manually triggered GitHub Pages build and deployment workflow.

## Product links and account integrity
The catalogue links directly to the existing Gumroad product pages. This website is a presentation layer only. It does not change Gumroad products, prices, files, covers, or publication settings.

## Images
Verified public Gumroad cover images are used for selected collections and artworks. Other items use typographic artwork tiles rather than invented image URLs.

## Publish
1. In repository Settings → Pages, set the build and deployment source to **GitHub Actions**.
2. Open Actions → **Publish HALL OF GREATNESS storefront**.
3. Run workflow only after reviewing the repository contents and approving publication.

The workflow is manual (`workflow_dispatch`) and does not deploy automatically on every commit.
