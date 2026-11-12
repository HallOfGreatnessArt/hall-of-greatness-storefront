#!/usr/bin/env python3
"""Translate visible artwork-specific landing-page copy with free local models.

Runs after landing pages have been generated and enhanced. Argos is preferred;
MADLAD-400 fills unsupported pairs. Page copy stays separate from existing UI
and catalogue translation data, preserving backward compatibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
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


def log_progress(message):
    """Emit timestamped, immediately flushed progress for live Actions logs."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[{timestamp}] {message}", flush=True)


SKIP_TAGS = {"head", "script", "style", "title", "h1", "select", "option"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def selected_language_codes(registry):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-index", type=int, default=0)
    parser.add_argument("--batch-count", type=int, default=1)
    args = parser.parse_args()
    if args.batch_count < 1 or not 0 <= args.batch_index < args.batch_count:
        parser.error("--batch-index must be within --batch-count")
    codes = [item["code"] for item in registry.get("languages", []) if item.get("code") != "en"]
    size = (len(codes) + args.batch_count - 1) // args.batch_count
    start = args.batch_index * size
    return set(codes[start:start + size])


def save_locale(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


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
            or any(key in attrs for key in ("data-hog-summary", "data-hog-category", "data-hog-full-description", "data-hog-product-details"))
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
    installed_codes = sorted({language.code for language in installed})
    total_updates = 0
    selected_codes = selected_language_codes(REGISTRY)
    log_progress(
        f"BATCH START selected_locales={sorted(selected_codes)} "
        f"published_pages={len(products)} installed_argos_languages={installed_codes}"
    )

    for language in REGISTRY.get("languages", []):
        code = language.get("code")
        if code not in selected_codes:
            continue
        locale_started = time.monotonic()
        locale_path = ROOT / "locales" / (code + ".json")
        locale_data = json.loads(locale_path.read_text(encoding="utf-8")) if locale_path.is_file() else {}
        translator = installed_translator(code, installed)
        engine = "argos" if translator is not None else "madlad-cpu-fallback"
        if translator is None and not has_fallback_engine():
            log_progress(f"LOCALE SKIP code={code} reason=no-free-translation-engine")
            continue

        log_progress(
            f"LOCALE START code={code} engine={engine} "
            f"page_count={len(products)}"
        )
        page_translations = locale_data.setdefault("landing_pages", {})
        changed = False

        for page_index, product in enumerate(products, start=1):
            page_started = time.monotonic()
            permalink = product["permalink"]
            page_path = ROOT / "landing" / product["landing_slug"] / "index.html"
            log_progress(
                f"PAGE START locale={code} page={page_index}/{len(products)} "
                f"permalink={permalink} slug={product['landing_slug']}"
            )
            if not page_path.is_file():
                log_progress(f"PAGE SKIP locale={code} permalink={permalink} reason=missing-html")
                continue
            page_html = page_path.read_text(encoding="utf-8")
            source_texts = extract_page_copy(page_html, titles)
            if not source_texts:
                log_progress(f"PAGE SKIP locale={code} permalink={permalink} reason=no-visible-copy")
                continue

            log_progress(
                f"PAGE COPY locale={code} permalink={permalink} "
                f"unique_text_blocks={len(source_texts)}"
            )
            source_hash = digest(source_texts)
            existing = page_translations.get(permalink, {})
            if existing.get("_source_hash") == source_hash:
                log_progress(f"PAGE SKIP locale={code} permalink={permalink} reason=source-unchanged")
                continue
            if existing.get("_review_status") == REVIEWED:
                log_progress(f"PAGE SKIP locale={code} permalink={permalink} reason=editorially-reviewed")
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

            log_progress(
                f"PAGE TRANSLATION START locale={code} permalink={permalink} "
                f"text_blocks={len(working_texts)} engine={engine}"
            )
            translated_values = translate_texts(
                working_texts,
                code,
                translator,
                progress_callback=lambda message: log_progress(
                    f"TRANSLATION locale={code} permalink={permalink} {message}"
                ),
            )
            if translated_values is None or len(translated_values) != len(source_texts):
                log_progress(
                    f"PAGE TRANSLATION FAILED locale={code} permalink={permalink}; "
                    "preserving prior complete copy"
                )
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
            save_locale(locale_path, locale_data)
            log_progress(
                f"PAGE COMPLETE locale={code} permalink={permalink} "
                f"elapsed_seconds={time.monotonic() - page_started:.1f} "
                f"translated_blocks={len(translated_values)} checkpoint=saved"
            )

        log_progress(
            f"LOCALE PAGE END code={code} permalink={permalink} "
            f"elapsed_seconds={time.monotonic() - page_started:.1f}"
        )

        if changed:
            locale_path.write_text(
                json.dumps(locale_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            log_progress(f"LOCALE CHECKPOINT code={code} file={locale_path.name} saved=true")

        log_progress(
            f"LOCALE COMPLETE code={code} elapsed_seconds={time.monotonic() - locale_started:.1f} "
            f"updated_pages={sum(1 for item in page_translations.values() if item.get('_review_status') == MACHINE)}"
        )

    log_progress(f"BATCH COMPLETE locale_page_updates={total_updates}")


if __name__ == "__main__":
    main()
