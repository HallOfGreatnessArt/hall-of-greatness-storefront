"""Focused regression tests for translation performance safeguards."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import free_translation as translation


class CountingArgos:
    def __init__(self):
        self.calls = []

    def translate(self, value):
        self.calls.append(value)
        return f"translated:{value}"


class TranslationPerformanceTests(unittest.TestCase):
    def test_locale_cache_translates_each_unique_text_once(self):
        translator = CountingArgos()
        cache = {}
        first = translation.translate_texts_cached(
            ["Shared heading", "Page one", "Shared heading"],
            "fr",
            translator,
            cache=cache,
        )
        second = translation.translate_texts_cached(
            ["Shared heading", "Page two", "Page one"],
            "fr",
            translator,
            cache=cache,
        )
        self.assertEqual(first, [
            "translated:Shared heading",
            "translated:Page one",
            "translated:Shared heading",
        ])
        self.assertEqual(second, [
            "translated:Shared heading",
            "translated:Page two",
            "translated:Page one",
        ])
        self.assertEqual(
            translator.calls,
            ["Shared heading", "Page one", "Page two"],
        )

    def test_timeout_splits_batch_and_preserves_segment_order(self):
        chunk = [(0, "alpha"), (1, "beta"), (2, "gamma"), (3, "delta")]
        calls = []

        def fake_batch(items, target):
            calls.append([item[0] for item in items])
            if len(items) > 2:
                return translation._TRANSLATION_TIMEOUT
            return {index: f"translated:{value}" for index, value in items}

        with patch.object(translation, "_translate_batch", side_effect=fake_batch):
            result = translation._translate_chunk_adaptive(chunk, "fr", lambda _: None)

        self.assertEqual(result, {
            0: "translated:alpha",
            1: "translated:beta",
            2: "translated:gamma",
            3: "translated:delta",
        })
        self.assertEqual(calls, [[0, 1, 2, 3], [0, 1], [2, 3]])

    def test_permanent_model_failure_is_not_retried_as_smaller_batches(self):
        chunk = [(0, "alpha"), (1, "beta"), (2, "gamma")]
        with patch.object(
            translation,
            "_translate_batch",
            return_value=translation._TRANSLATION_FAILED,
        ) as batch:
            result = translation._translate_chunk_adaptive(chunk, "fr", lambda _: None)
        self.assertIsNone(result)
        batch.assert_called_once()

    def test_failed_cache_fill_does_not_store_partial_results(self):
        cache = {}
        with patch.object(translation, "translate_texts", return_value=None):
            result = translation.translate_texts_cached(
                ["one", "two"], "fr", cache=cache
            )
        self.assertIsNone(result)
        self.assertEqual(cache, {})


if __name__ == "__main__":
    unittest.main()
