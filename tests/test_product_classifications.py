#!/usr/bin/env python3
"""Regression tests for the three-section Gumroad product taxonomy."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.apply_product_classifications import apply_classifications


class ProductClassificationTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / "catalog-data.json").read_text(encoding="utf-8"))
        self.manifest = json.loads((ROOT / "product-classifications.json").read_text(encoding="utf-8"))
        # Keep the regression fixture stable both before and after public Gumroad
        # discovery. The four books are imported during CI and synthesized here
        # only when running the test directly against the checked-in base catalogue.
        expected_new_books = {
            "qsznm": "The AI Black Box",
            "wdwtbf": "The Humanity Test",
            "ylxtub": "THE ALGORITHM EMPIRE",
            "qccitx": "THE LAST JOB",
        }
        known = {p.get("permalink") for p in self.catalog["products"]}
        for permalink, name in expected_new_books.items():
            if permalink not in known:
                self.catalog["products"].append({
                    "name": name,
                    "permalink": permalink,
                    "published": True,
                    "tags": [],
                })

    def test_existing_catalogue_is_classified_into_exactly_three_sections(self):
        apply_classifications(self.catalog, self.manifest)
        published = [p for p in self.catalog["products"] if p.get("published") is True]
        self.assertTrue(published)
        self.assertTrue(all(p.get("content_type") in {"art-decor", "ebook", "course"} for p in published))
        # One legacy ebook plus the four newly imported books.
        self.assertEqual(sum(p["content_type"] == "ebook" for p in published), 5)
        new_book_permalinks = {"qsznm", "wdwtbf", "ylxtub", "qccitx"}
        classified_new_books = {
            p["permalink"] for p in published if p["content_type"] == "ebook"
        } & new_book_permalinks
        self.assertEqual(classified_new_books, new_book_permalinks)
        book = next(p for p in published if p["permalink"] == "isbsay")
        self.assertEqual(book["content_type"], "ebook")
        self.assertIn("ebooks", book["tags"])
        self.assertTrue(book["cover_url"].startswith("https://"))
        self.assertTrue(book["url"].startswith("https://alshayebemad.gumroad.com/l/"))

    def test_gumroad_course_tag_overrides_legacy_art_fallback(self):
        catalog = {"products": [{"permalink": "course-1", "published": True, "tags": ["courses"]}]}
        applied = apply_classifications(catalog, {"products": {"course-1": {"content_type": "art-decor", "tags": ["art-decor"]}}})
        self.assertEqual(applied, 1)
        self.assertEqual(catalog["products"][0]["content_type"], "course")
        self.assertIn("courses", catalog["products"][0]["tags"])

    def test_gumroad_ebook_aliases_are_supported(self):
        for tag in ("ebooks", "digital-ebook", "digital-book"):
            catalog = {"products": [{"permalink": "book-1", "published": True, "tags": [tag]}]}
            apply_classifications(catalog, {"products": {}})
            self.assertEqual(catalog["products"][0]["content_type"], "ebook")

    def test_unknown_tags_fail_closed_and_do_not_guess_a_section(self):
        catalog = {"products": [{"permalink": "unknown-1", "published": True, "tags": ["miscellaneous"]}]}
        apply_classifications(catalog, {"products": {}})
        self.assertNotIn("content_type", catalog["products"][0])

    def test_conflicting_section_tags_fail_closed(self):
        catalog = {"products": [{"permalink": "conflict-1", "published": True, "tags": ["ebooks", "courses"]}]}
        with self.assertRaisesRegex(ValueError, "Conflicting section tags"):
            apply_classifications(catalog, {"products": {}})

    def test_application_is_idempotent(self):
        apply_classifications(self.catalog, self.manifest)
        apply_classifications(self.catalog, self.manifest)
        book = next(p for p in self.catalog["products"] if p["permalink"] == "isbsay")
        self.assertEqual(book["tags"].count("ebooks"), 1)

    def test_unknown_manifest_permalink_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown catalogue permalinks"):
            apply_classifications(self.catalog, {"products": {"not-a-real-product": {"content_type": "ebook", "tags": ["ebooks"]}}})


if __name__ == "__main__":
    unittest.main()
