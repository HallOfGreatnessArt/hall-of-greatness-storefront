import html
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from translate_landing_pages import extract_page_copy
from free_translation import translate_text, translate_texts
from unittest.mock import Mock, patch


class ProductPageLocalizationTests(unittest.TestCase):
    def test_landing_copy_dictionary_is_complete_and_source_keyed(self):
        copy = json.loads((ROOT / "assets/landing-copy.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(copy), 40)
        self.assertTrue(all(isinstance(k, str) and k.strip() for k in copy))
        self.assertTrue(all(isinstance(v, str) and v.strip() for v in copy.values()))
        for phrase in (
            "The meaning behind the artwork",
            "Digital download details",
            "Make the artwork part of your space",
            "No physical artwork or frame is shipped.",
            "Privacy",
            "Gumroad store ↗",
        ):
            self.assertTrue(any(key.startswith(phrase) for key in copy), phrase)

    def test_artwork_specific_extractor_keeps_story_and_skips_brand_title_and_shared_copy(self):
        sample = """<!doctype html><html><head><title>Sample</title></head><body>
        <span class="brand">HALL OF GREATNESS</span><h1>SAMPLE ARTWORK</h1>
        <p>A unique story about courage, memory, and renewal.</p>\n        <p data-hog-summary>catalog summary placeholder</p>\n        <div data-hog-category>category placeholder</div>\n        <div data-hog-full-description><p>long description placeholder</p></div>\n        <div data-hog-product-details><p>product detail placeholder</p></div>
        <p>Digital download</p><div class="price">$5.00</div>
        <a>Explore &amp; Get the Artwork ↗</a></body></html>"""
        extracted = extract_page_copy(sample, ["SAMPLE ARTWORK"])
        self.assertIn("A unique story about courage, memory, and renewal.", extracted)
        self.assertNotIn("SAMPLE ARTWORK", extracted)
        self.assertNotIn("HALL OF GREATNESS", extracted)
        self.assertNotIn("Digital download", extracted)
        self.assertNotIn("$5.00", extracted)
        self.assertNotIn("catalog summary placeholder", extracted)
        self.assertNotIn("category placeholder", extracted)
        self.assertNotIn("long description placeholder", extracted)
        self.assertNotIn("product detail placeholder", extracted)

    def test_argos_is_preferred_and_madlad_is_used_when_argos_is_missing(self):
        argos = Mock()
        argos.translate.return_value = "Traduction Argos"
        with patch("free_translation._madlad_translate") as madlad:
            self.assertEqual(translate_text("Hello", "fr", argos), "Traduction Argos")
            madlad.assert_not_called()

        with patch("free_translation._madlad_translate", return_value="Traduction MADLAD") as madlad:
            self.assertEqual(translate_text("Hello", "fr", None), "Traduction MADLAD")
            madlad.assert_called_once_with("Hello", "fr")

    def test_madlad_batch_translation_preserves_original_order(self):
        markers = ["[1]", "[2]"]
        output = f"{markers[0]}\nUno.\n{markers[1]}\nDos."
        with patch("free_translation._madlad_translate", return_value=output):
            self.assertEqual(translate_texts(["One.", "Two."], "es", None), ["Uno.", "Dos."])

    def test_long_descriptions_split_and_keep_paragraph_boundaries(self):
        import re
        from free_translation import _split_long_text

        source = (" ".join(["first"] * 300)) + "\n\n" + (" ".join(["second"] * 300))
        groups = _split_long_text(source)
        self.assertEqual(len(groups), 2)
        self.assertTrue(all(len(group) == 2 for group in groups))

        def fake_madlad(text, target):
            matches = re.findall(r"(\[\d+\])\n(.*?)(?=\n\[\d+\]|\Z)", text, flags=re.S)
            if matches:
                return "\n".join(f"{marker}\nTranslated {part}" for marker, part in matches)
            return "Translated " + text

        with patch("free_translation._madlad_translate", side_effect=fake_madlad):
            result = translate_texts([source], "es", None)
        self.assertIsNotNone(result)
        self.assertEqual(result[0].count("\n\n"), 1)
        self.assertTrue(result[0].startswith("Translated"))
        self.assertIn("Translated", result[0])

    def test_madlad_batch_marker_mismatch_falls_back_to_individual_texts(self):
        with patch("free_translation._madlad_translate", side_effect=["unusable combined output", "Uno.", "Dos."]):
            self.assertEqual(translate_texts(["One.", "Two."], "es", None), ["Uno.", "Dos."])

    def test_madlad_is_used_when_argos_throws(self):
        argos = Mock()
        argos.translate.side_effect = RuntimeError("missing or broken Argos model")
        with patch("free_translation._madlad_translate", return_value="Traduction MADLAD"):
            self.assertEqual(translate_text("Hello", "fr", argos), "Traduction MADLAD")

    def test_chinese_locale_tags_map_to_model_language_code(self):
        from free_translation import TARGET_CODE_MAP
        self.assertNotIn("zh-CN", TARGET_CODE_MAP)
        self.assertNotIn("zh-TW", TARGET_CODE_MAP)

    def test_runtime_and_build_pipeline_consume_landing_copy(self):
        runtime = (ROOT / "assets/landing-i18n.js").read_text(encoding="utf-8")
        translator = (ROOT / "scripts/translate_catalog.py").read_text(encoding="utf-8")
        enhancer = (ROOT / "scripts/enhance_landing_pages.py").read_text(encoding="utf-8")
        page_translator = (ROOT / "scripts/translate_landing_pages.py").read_text(encoding="utf-8")
        coverage_validator = (ROOT / "scripts/validate_translation_coverage.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/publish-storefront.yml").read_text(encoding="utf-8")
        self.assertIn('data.landing_ui||{}', runtime)
        self.assertIn("originalTextNodes", runtime)
        self.assertIn("data.landing_pages||{}", runtime)
        self.assertIn("if(p.summary)", runtime)
        self.assertIn("if(p.category)", runtime)
        self.assertIn("data.product_detail_labels||{}", runtime)
        self.assertIn('assets/landing-copy.json', translator)
        self.assertIn('old["landing_ui"]', translator)
        self.assertIn("summary_html", enhancer)
        free_engine = (ROOT / "scripts/free_translation.py").read_text(encoding="utf-8")
        self.assertIn("madlad", free_engine)
        self.assertIn("has_fallback_engine", translator)
        self.assertIn("has_fallback_engine", page_translator)
        self.assertIn("VisibleCopyParser", page_translator)
        self.assertIn("extract_page_copy", page_translator)
        self.assertIn("landing_pages", page_translator)
        self.assertIn("missing_page_copy", coverage_validator)
        self.assertIn("missing_detail_labels", coverage_validator)
        self.assertIn("validate_translation_coverage.py", workflow)
        self.assertIn('data-hog-summary', enhancer)
        self.assertIn('assets/landing-copy.json', workflow)

    def test_enhanced_pages_have_valid_body_and_translate_repeated_summary(self):
        catalog = json.loads((ROOT / "catalog-data.json").read_text(encoding="utf-8"))
        published = [p for p in catalog["products"] if p.get("published")]
        for product in published:
            page_path = ROOT / "landing" / product["landing_slug"] / "index.html"
            self.assertTrue(page_path.is_file(), str(page_path))
            page = page_path.read_text(encoding="utf-8")
            self.assertRegex(page, r'<body\s+data-product-permalink="[^"]+">')
            paragraphs = re.findall(r'<p([^>]*)>(.*?)</p>', page, flags=re.S)
            matches = [(attrs, html.unescape(body).strip()) for attrs, body in paragraphs
                       if html.unescape(body).strip() == product["summary"].strip()]
            self.assertIn("class=\"desc\" data-hog-summary", page, product["landing_slug"])
            self.assertTrue(all("data-hog-summary" in attrs for attrs, _ in matches), product["landing_slug"])
            self.assertIn('id="printing"', page)
            self.assertIn('id="room-showcase"', page)


if __name__ == "__main__":
    unittest.main()
