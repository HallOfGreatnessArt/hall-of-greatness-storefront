#!/usr/bin/env python3
"""Translate visible artwork-specific landing-page copy with free local models.

Runs after landing pages have been generated and enhanced. Argos is preferred;
MADLAD-400 fills unsupported pairs. Page copy stays separate from existing UI
and catalogue translation data, preserving backward compatibility.
"""
from __future__ import annotations

import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

from free_translation import has_fallback_engine, translate_texts


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = json.loads((ROOT / "locales/languages.json").read_text(encoding="utf-8"))
CATALOG = json.loads((ROOT / "catalog-data.json").read_text(encoding="utf-8"))
SHARED_COPY = json.loads((ROOT / "assets/landing-copy.json").read_text(encoding="utf-8"))
CODE_MAP = {"zh-CN": "zh"}
REVIEWED = "editorially-reviewed"
MACHINE = "machine-generated-unreviewed"
SKIP_TAGS = {"head", "script", "style", "title", "h1", "select", "option"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class VisibleCopyParser(HTMLParser):
    """Collect visible text nodes while preserving original artwork names."""

    def __init__(self, excluded_titles, shared_copy):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.texts = []
        self.excluded_titles = set(excluded_titles) | {"HALL OF GREATNESS"}
        self.shared_copy = set(shared_copy)

    def _skipping(self):
        return any(skipped for _, skipped in self.stack)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        skip = (
            self._skipping()
            or tag in SKIP_TAGS
            or "brand" in classes
            or "price" in classes
        )
        if tag not in VOID_TAGS:
            self.stack.append((tag, skip))

    def handle_startendtag(self, tag, attrs):
        return

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, data):
        value = data.strip()
        if not value or self._skipping():
            return
        if value in self.excluded_titles or value in self.shared_copy:
            return
        self.texts.append(value)


def extract_page_copy(page_html, excluded_titles):
    parser = VisibleCopyParser(excluded_titles, SHARED_COPY)
    parser.feed(page_html)
    # Keep first-seen order while avoiding repeated translation work.
    return list(dict.fromkeys(parser.texts))


def installed_translator(code, installed):
    target = CODE_MAP.get(code, code)
    source = next((language for language in installed if language.code == "en"), None)
    destination = next((language for language in installed if language.code == target), None)
    if not source or not destination:
        return None
    return source.get_translation(destination)


def main():
    import argostranslate.translate

    products = [
        product for product in CATALOG.get("products", [])
        if product.get("published") and product.get("permalink") and product.get("landing_slug")
    ]
    titles = [str(product.get("name", "")).strip() for product in CATALOG.get("products", [])] + ["HALL OF GREATNESS"]
    installed = argostranslate.translate.get_installed_languages()
    total_updates = 0

    for language in REGISTRY.get("languages", []):
        code = language.get("code")
        if not code or code == "en":
            continue
        locale_path = ROOT / "locales" / (code + ".json")
        locale_data = json.loads(locale_path.read_text(encoding="utf-8")) if locale_path.is_file() else {}
        translator = installed_translator(code, installed)
        if translator is None and not has_fallback_engine():
            print(f"NO FREE MODEL AVAILABLE: en -> {code}; leaving English source copy intact.")
            continue

        page_translations = locale_data.setdefault("landing_pages", {})
        changed = False

        for product in products:
            permalink = product["permalink"]
            page_path = ROOT / "landing" / product["landing_slug"] / "index.html"
            if not page_path.is_file():
                print(f"MISSING PAGE: {product['landing_slug']}; skipped for {code}.")
                continue
            page_html = page_path.read_text(encoding="utf-8")
            source_texts = extract_page_copy(page_html, titles)
            if not source_texts:
                continue

            source_hash = digest(source_texts)
            existing = page_translations.get(permalink, {})
            if existing.get("_source_hash") == source_hash:
                continue
            if existing.get("_review_status") == REVIEWED:
                print(f"REVIEW REQUIRED: {code}/{permalink}; preserving reviewed page copy.")
                continue

            working_texts = []
            protected_titles = []
            for source_text in source_texts:
                working_text = source_text
                protected = []
                for title_index, title in enumerate(titles):
                    if title and title in working_text:
                        token = f"ZXQHOGTITLE{title_index}QXZ"
                        working_text = working_text.replace(title, token)
                        protected.append((token, title))
                working_texts.append(working_text)
                protected_titles.append(protected)

            translated_values = translate_texts(working_texts, code, translator)
            if translated_values is None or len(translated_values) != len(source_texts):
                print(f"TRANSLATION FAILED: {code}/{permalink}; preserving prior complete copy.")
                continue

            translated = {}
            for source_text, result, protected in zip(source_texts, translated_values, protected_titles):
                for token, title in protected:
                    result = result.replace(token, title)
                translated[source_text] = result

            translated["_source_hash"] = source_hash
            translated["_review_status"] = MACHINE
            page_translations[permalink] = translated
            changed = True
            total_updates += 1

        if changed:
            locale_path.write_text(
                json.dumps(locale_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"Updated artwork-specific page copy for {code}.")

    print(f"Artwork-specific localization complete: {total_updates} locale/product page updates.")


if __name__ == "__main__":
    main()
