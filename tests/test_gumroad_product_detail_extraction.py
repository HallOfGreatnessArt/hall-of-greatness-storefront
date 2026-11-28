#!/usr/bin/env python3
"""Regression tests for Gumroad public-page extraction boundaries."""
import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("gumroad_importer",ROOT/"scripts/import_public_gumroad_product.py")
MODULE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class ProductDetailExtractionTests(unittest.TestCase):
    def test_extracts_only_text_between_adjacent_labels(self):
        text="Product type Digital artwork download Delivery Instant digital download Physical item No physical print Printing Use a professional printer Usage Personal use Add to wishlist"
        self.assertEqual(MODULE.detail_between(text,"Product type","Delivery"),"Digital artwork download")
        self.assertEqual(MODULE.detail_between(text,"Delivery","Physical item"),"Instant digital download")
        self.assertEqual(MODULE.detail_between(text,"Physical item","Printing"),"No physical print")

    def test_missing_end_label_returns_empty_instead_of_rest_of_page(self):
        text="Delivery Instant download Add to wishlist Share Product title Description Explore our collection"
        self.assertEqual(MODULE.detail_between(text,"Delivery","Physical item"),"")

    def test_page_chrome_is_rejected(self):
        text="Delivery Instant download Add to wishlist Physical item"
        self.assertEqual(MODULE.detail_between(text,"Delivery","Physical item"),"")

    def test_long_scraped_content_is_rejected(self):
        text="Delivery "+"A"*520+" Physical item"
        self.assertEqual(MODULE.detail_between(text,"Delivery","Physical item"),"")

    def test_repeated_character_corruption_is_rejected(self):
        text="Delivery nnnnnnnnnnn Physical item"
        self.assertEqual(MODULE.detail_between(text,"Delivery","Physical item"),"")

    def test_gumroad_publish_workflow_is_manual_only(self):
        workflow=(ROOT/".github/workflows/refresh-gumroad-product-landings.yml").read_text(encoding="utf-8")
        trigger_block=workflow.split("permissions:",1)[0]
        self.assertIn("workflow_dispatch:",trigger_block)
        self.assertNotIn("\\n  push:",trigger_block)

if __name__=="__main__":
    unittest.main()
