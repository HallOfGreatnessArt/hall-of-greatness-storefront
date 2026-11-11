import html
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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

    def test_runtime_and_build_pipeline_consume_landing_copy(self):
        runtime = (ROOT / "assets/landing-i18n.js").read_text(encoding="utf-8")
        translator = (ROOT / "scripts/translate_catalog.py").read_text(encoding="utf-8")
        enhancer = (ROOT / "scripts/enhance_landing_pages.py").read_text(encoding="utf-8")
        page_translator = (ROOT / "scripts/translate_landing_pages.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/publish-storefront.yml").read_text(encoding="utf-8")
        self.assertIn('data.landing_ui||{}', runtime)
        self.assertIn("originalTextNodes", runtime)
        self.assertIn("data.landing_pages||{}", runtime)
        self.assertIn('assets/landing-copy.json', translator)
        self.assertIn('old["landing_ui"]', translator)
        self.assertIn("summary_html", enhancer)
        self.assertIn("VisibleCopyParser", page_translator)
        self.assertIn("extract_page_copy", page_translator)
        self.assertIn("landing_pages", page_translator)
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
