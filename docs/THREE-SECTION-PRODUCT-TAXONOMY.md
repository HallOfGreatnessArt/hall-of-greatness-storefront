# HALL OF GREATNESS — Three-section product taxonomy

The public storefront has three mutually exclusive product sections:

| Storefront section | Canonical Gumroad tag | Catalogue `content_type` |
| --- | --- | --- |
| Art & Decor | `art-decor` | `art-decor` |
| E-Books | `ebooks` | `ebook` |
| Educational Courses | `courses` | `course` |

## Required GitHub Actions connection

Automatic reading of product tags requires a repository Actions secret named `GUMROAD_ACCESS_TOKEN`. Add it in the repository's **Settings → Secrets and variables → Actions → New repository secret**. The token must belong to `https://alshayebemad.gumroad.com` and permit reading the seller's products. Do not place the token in source files, workflow YAML, or chat messages.

If this secret is absent, Actions logs explicitly report that account tag synchronization was skipped. The existing catalogue can still use its curated compatibility classifications, but newly published products cannot be guaranteed automatic section placement until the secret is configured.

## Publishing a new product

1. Create and publish the product in the HALL OF GREATNESS Gumroad account.
2. In the product's Gumroad settings, add exactly one canonical section tag from the table above.
3. The scheduled GitHub Actions storefront workflow reads product metadata through the Gumroad API using the repository secret `GUMROAD_ACCESS_TOKEN`.
4. Before reading products, the workflow verifies that the token belongs to `alshayebemad.gumroad.com`. A mismatch stops the sync; it never imports from another seller account.
5. The catalogue classifier writes the matching `content_type`, then the storefront renders the product in that section.

The Gumroad API integration is read-only. It does not edit products, tags, prices, files, publication status, profile HTML, or account settings.

## Compatibility and safety

- Existing ebook aliases `digital-ebook` and `digital-book` remain supported.
- Common art aliases (`art`, `decor`, `wall-art`, `printable-art`) and course aliases (`course`, `online-course`, `educational-course`, `training`) are recognized.
- The exact-permalink registry preserves the existing published catalogue when public feeds omit tags.
- A real Gumroad section tag takes precedence over the legacy registry fallback, allowing an existing product to change section by changing its Gumroad tag.
- A product carrying tags from more than one section is rejected by classification rather than displayed in the wrong place.
- A published product without a recognized section tag is not guessed into a section. The production build fails closed until it is classified.
- Unrecognized non-section tags are retained in the catalogue.

## Validation

GitHub Actions checks:
- all published products map to one supported section;
- no product appears in more than one section;
- existing E-Book classification remains intact;
- new course and ebook tags are recognized;
- conflicting tags fail closed;
- exact Gumroad product URLs and detail-page links remain on their cards;
- desktop/mobile layout, keyboard activation, and card-surface navigation continue to work;
- multilingual UI keys are extended without overwriting reviewed translations.

The storefront's section headings and descriptions are maintained in the canonical English UI dictionary and refreshed into supported locales by the existing offline translation workflow.
