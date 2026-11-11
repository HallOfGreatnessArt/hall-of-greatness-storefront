import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_localization import audit, digest, product_source_fields


class LocalizationAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "assets").mkdir()
        (self.root / "locales").mkdir()
        (self.root / "assets/i18n.js").write_text(
            'const M={"en":{"nav":"Gallery","hero":"Art"}};\nconst map=',
            encoding="utf-8",
        )
        (self.root / "locales/languages.json").write_text(
            json.dumps({"languages": [
                {"code": "en", "name": "English", "rtl": False},
                {"code": "fr", "name": "French", "rtl": False},
                {"code": "ar", "name": "Arabic", "rtl": True},
            ]}),
            encoding="utf-8",
        )
        self.product = {
            "permalink": "p1", "published": True, "summary": "Hello",
            "category": "Art", "product_details": {},
        }
        (self.root / "catalog-data.json").write_text(
            json.dumps({"products": [self.product]}), encoding="utf-8"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_locale_file_is_reported(self):
        (self.root / "locales/fr.json").write_text(
            json.dumps({"ui": {"nav": "Galerie"}, "products": {}}),
            encoding="utf-8",
        )
        report = audit(self.root)
        self.assertEqual(report["missing_locale_codes"], ["ar"])
        self.assertEqual(report["summary"]["missing_locale_files"], 1)

    def test_missing_ui_and_product_content_are_reported(self):
        (self.root / "locales/fr.json").write_text(
            json.dumps({"ui": {"nav": "Galerie"}, "products": {}}),
            encoding="utf-8",
        )
        report = audit(self.root)
        fr = next(item for item in report["languages"] if item["code"] == "fr")
        self.assertEqual(fr["counts"]["missing_ui_keys"], 1)
        self.assertEqual(fr["counts"]["missing_products"], 1)
        self.assertEqual(fr["translation_status"], "incomplete")

    def test_review_status_is_not_inferred_from_translation_presence(self):
        (self.root / "locales/fr.json").write_text(
            json.dumps({
                "ui": {"nav": "Galerie", "hero": "Art"},
                "products": {"p1": {"summary": "Bonjour", "category": "Art",
                                    "_source_hash": "old"}},
            }),
            encoding="utf-8",
        )
        report = audit(self.root)
        fr = next(item for item in report["languages"] if item["code"] == "fr")
        self.assertEqual(fr["ui_review_status"], "unreviewed")
        self.assertEqual(fr["products_review_status"], "unreviewed")
        self.assertEqual(fr["counts"]["stale_product_translations"], 1)
        self.assertEqual(fr["counts"]["product_fields_identical_to_english"], 1)

    def test_duplicate_language_codes_are_detected(self):
        languages = json.loads((self.root / "locales/languages.json").read_text())
        languages["languages"].append({"code": "fr", "name": "French duplicate", "rtl": False})
        (self.root / "locales/languages.json").write_text(json.dumps(languages))
        report = audit(self.root)
        self.assertEqual(report["summary"]["duplicate_language_codes"], ["fr"])


    def test_translation_engine_metadata_matches_implementation(self):
        repository_root = Path(__file__).resolve().parents[1]
        registry = json.loads((repository_root / "locales/languages.json").read_text(encoding="utf-8"))
        implementation = (repository_root / "scripts/translate_catalog.py").read_text(encoding="utf-8")
        self.assertIn("Argos Translate", registry.get("provider", ""))
        self.assertIn("argostranslate.translate", implementation)

if __name__ == "__main__":
    unittest.main()
