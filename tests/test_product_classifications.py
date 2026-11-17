#!/usr/bin/env python3
"""Regression tests for the curated public-catalogue product classifications."""
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

    def test_verified_book_is_in_ebooks_library(self):
        apply_classifications(self.catalog, self.manifest)
        book = next(p for p in self.catalog["products"] if p["permalink"] == "isbsay")
        self.assertEqual(book["content_type"], "ebook")
        self.assertIn("ebooks", book["tags"])
        self.assertTrue(book["published"])
        self.assertTrue(book["cover_url"].startswith("https://"))
        self.assertTrue(book["url"].startswith("https://alshayebemad.gumroad.com/l/"))

    def test_artwork_is_not_misclassified(self):
        apply_classifications(self.catalog, self.manifest)
        artwork = next(p for p in self.catalog["products"] if p["permalink"] == "ycltf")
        self.assertNotIn("ebooks", artwork.get("tags", []))
        self.assertNotEqual(artwork.get("content_type"), "ebook")

    def test_application_is_idempotent(self):
        apply_classifications(self.catalog, self.manifest)
        apply_classifications(self.catalog, self.manifest)
        book = next(p for p in self.catalog["products"] if p["permalink"] == "isbsay")
        self.assertEqual(book["tags"].count("ebooks"), 1)

    def test_unknown_permalink_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown catalogue permalinks"):
            apply_classifications(self.catalog, {"products": {"not-a-real-product": {"content_type": "ebook", "tags": ["ebooks"]}}})


if __name__ == "__main__":
    unittest.main()
