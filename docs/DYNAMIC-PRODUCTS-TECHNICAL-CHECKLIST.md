# Dynamic Published-Products Section — Technical Audit Checklist

Scope: the HALL OF GREATNESS storefront's dynamic product catalogue renderer in `index.html`, backed by the generated `catalog-data.json`.

Safety boundary:
- Read-only with respect to Gumroad. No product, price, file, cover, bundle, publication state, payout, checkout, or account-setting writes.
- Changes in this work are limited to the storefront repository's presentation code, validation, tests, and documentation.
- No merge to `main` and no production deployment are part of this repair.

## A. Data source and transport
- [x] Request the same-origin `catalog-data.json` endpoint rather than exposing credentials or calling a private account API from the browser.
- [x] Reject non-2xx responses.
- [x] Require a JSON response content type and a valid JSON body.
- [x] Bound each request with a timeout and retry once before showing an error.
- [ ] Verify the published production endpoint returns HTTP 200 with `application/json` from a real browser on mobile and desktop.
- [ ] Verify cache headers/CDN behavior after a catalogue deployment.

## B. Catalogue schema and integrity
- [x] Require a top-level `products` array.
- [x] Render only records explicitly marked `published: true`.
- [x] Require product name, landing slug, and a valid HTTPS Gumroad product URL.
- [x] Require a finite, non-negative display price; this is read-only display data and is not written back to Gumroad.
- [x] Restrict cover images to the HTTPS Gumroad public-files origin.
- [x] Reject duplicate product permalinks and landing slugs.
- [ ] Compare the built catalogue's published count against the connected Gumroad read-only product inventory during CI.
- [ ] Confirm bundle membership and downloaded files separately; the renderer cannot prove package contents.

## C. Rendering and user interaction
- [x] Keep bundles and individual artworks in separate sections.
- [x] Preserve search, category filters, translated labels, landing-page links, and direct Gumroad purchase links.
- [x] Escape catalogue-provided text and validate product/image URL origins before inserting them into markup.
- [x] Provide an explicit loading state for both sections.
- [x] Provide a single accessible error state and a user-triggered retry after bounded automatic retries.
- [ ] Confirm the error/retry state with browser automation under simulated network failure.
- [ ] Confirm all product cards and their explicit links open the intended destination.

## D. Images and accessibility
- [x] Escape validated cover URLs and retain descriptive image alt text.
- [ ] Confirm every published product has a non-empty cover URL and every image loads successfully.
- [ ] Confirm no broken image placeholders, layout shifts, or horizontal overflow at 320, 360, 390, 768, 1024, and 1440 CSS pixels.
- [ ] Confirm keyboard navigation, visible focus, and screen-reader announcements for loading/error states.

## E. Regression and release gates
- [ ] Run responsive storefront tests and product-card navigation tests.
- [ ] Run the public Gumroad discovery/synchronization workflow in read-only discovery mode where possible; do not change Gumroad records.
- [ ] Confirm the catalogue still contains only published products and no duplicate identifiers.
- [ ] Inspect the proposed diff to ensure only storefront code, tests, and this checklist changed.
- [ ] Obtain explicit approval before merging to `main` or deploying.

## Repair implementation notes
The dynamic renderer now performs bounded fetch retries, response/schema validation, strict Gumroad URL checks, duplicate identifier checks, safe cover URL checks, and consistent loading/error UI for both product sections. A failed load exposes a retry button instead of leaving the collection area indefinitely blank. These checks do not update or mutate Gumroad data.

Status convention: checked items are implemented in the current repair branch; unchecked items require CI or live-browser evidence before the repair can be considered fully validated.
