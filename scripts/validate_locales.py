#!/usr/bin/env python3
"""Read-only quality checks for storefront locale files and product translations."""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
registry = json.loads((ROOT / "locales/languages.json").read_text(encoding="utf-8"))
source = (ROOT / "assets/i18n.js").read_text(encoding="utf-8")
landing_source = (ROOT / "assets/landing-i18n.js").read_text(encoding="utf-8")
match = re.search(r"const M=(\{[\s\S]*?\});\nconst map=", source)
if not match:
    raise SystemExit("ERROR: canonical UI dictionary not found in assets/i18n.js")
canonical = json.loads(match.group(1))
english = canonical.get("en", {})
expected_keys = set(english)
catalog = json.loads((ROOT / "catalog-data.json").read_text(encoding="utf-8"))
published = [p for p in catalog.get("products", []) if p.get("published")]
expected_products = {p.get("permalink") for p in published if p.get("permalink")}
source_products = {p.get("permalink"): p for p in published if p.get("permalink")}

errors = []
warnings = []
counts = {"registered": 0, "files": 0, "reviewed": 0, "machine": 0, "unmarked": 0}
rtl_missing = []

for entry in registry.get("languages", []):
    code = entry.get("code")
    if not code:
        errors.append("Language registry contains an entry without a code")
        continue
    if code == "en":
        continue
    counts["registered"] += 1
    path = ROOT / "locales" / (code + ".json")
    if not path.exists():
        warnings.append(f"MISSING LOCALE FILE: {code} ({path.relative_to(ROOT)})")
        if entry.get("rtl"):
            rtl_missing.append(code)
        continue
    counts["files"] += 1
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"INVALID LOCALE {code}: {exc}")
        continue
    ui = data.get("ui")
    if not isinstance(ui, dict):
        errors.append(f"{code}: missing or invalid ui dictionary")
        ui = {}
    missing = sorted(expected_keys - set(ui))
    extra = sorted(set(ui) - expected_keys)
    empty = sorted(k for k, v in ui.items() if not isinstance(v, str) or not v.strip())
    if missing:
        errors.append(f"{code}: {len(missing)} missing UI keys: {', '.join(missing[:8])}")
    if extra:
        errors.append(f"{code}: {len(extra)} unexpected UI keys: {', '.join(extra[:8])}")
    if empty:
        errors.append(f"{code}: {len(empty)} empty/non-string UI values: {', '.join(empty[:8])}")
    unchanged = [k for k in expected_keys if ui.get(k) == english.get(k)]
    if unchanged:
        warnings.append(f"{code}: {len(unchanged)} UI values exactly match English (possible untranslated copy)")
    status = data.get("_ui_translation_status", "unmarked")
    if data.get("_ui_reviewed") is True and status == "editorially-reviewed":
        counts["reviewed"] += 1
    elif status == "machine-generated-unreviewed":
        counts["machine"] += 1
    else:
        counts["unmarked"] += 1

    products = data.get("products", {})
    missing_products = sorted(expected_products - set(products))
    if missing_products:
        warnings.append(f"{code}: {len(missing_products)} published product translations missing")
    extra_products = sorted(set(products) - expected_products)
    if extra_products:
        warnings.append(f"{code}: {len(extra_products)} product translation keys are not in the published catalogue")
    for slug in expected_products:
        item = products.get(slug)
        if not isinstance(item, dict):
            continue
        if code == "ar" and not str(item.get("title_ar", "")).strip():
            errors.append(f"{code}/{slug}: missing Arabic product display title")
        if code == "ar":
            first_line = next((line.strip() for line in str(item.get("full_description", "")).splitlines() if line.strip()), "")
            if re.search(rf"[—–]\s*{re.escape(slug)}$", first_line):
                errors.append(f"{code}/{slug}: internal catalogue slug leaked into the Arabic description heading")
            summary_latin = re.findall(r"\b[A-Za-z]{3,}\b", str(item.get("summary", "")))
            if summary_latin:
                warnings.append(f"{code}/{slug}: English words remain in the Arabic product summary: {', '.join(summary_latin[:6])}")
            file_copy = str((item.get("product_details") or {}).get("files_included", ""))
            if re.search(r"(?:\b\d+ files?\b|\bMB\b|\bKB\b|للزدحام|::|DF, TXT)", file_copy, re.I):
                warnings.append(f"{code}/{slug}: file-included metadata is not fully localized or may be corrupted")
        for field in ("summary", "full_description", "category"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{code}/{slug}: missing, empty, or invalid {field}")
                continue
            if "\ufffd" in value:
                errors.append(f"{code}/{slug}: Unicode replacement character in {field}")
            if re.search(r"(?:Ã.|Â.|Ø[ء-ي]|Ù[ء-ي])", value):
                warnings.append(f"{code}/{slug}: possible mojibake in {field}")
            entities = re.findall(r"&(?:quot|apos|amp|lt|gt);", value)
            if entities:
                warnings.append(f"{code}/{slug}: {len(entities)} HTML entities remain in {field}; renderer must decode before escaping")
            latin_words = re.findall(r"\b[A-Za-z]{3,}\b", value)
            arabic_chars = re.findall(r"[\u0600-\u06FF]", value)
            if len(latin_words) >= 8 and len(arabic_chars) < len(latin_words) * 2:
                warnings.append(f"{code}/{slug}: substantial Latin-script copy remains in {field} ({len(latin_words)} words)")
        source_product = source_products.get(slug, {})
        source_fields = {k: source_product.get(k) for k in ("summary", "full_description", "category") if source_product.get(k)}
        source_fields["product_details"] = source_product.get("product_details") or {}
        expected_hash = __import__("hashlib").sha256(json.dumps(source_fields, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if item.get("_source_hash") != expected_hash:
            warnings.append(f"{code}/{slug}: product translation source hash is missing or stale")
        status = item.get("_translation_status", "unmarked")
        if status not in ("editorially-reviewed", "editorial-draft-ai-assisted"):
            warnings.append(f"{code}/{slug}: translation review status is {status}")

# The Arabic hero phrase is a release-critical copy requirement.
arabic_file = ROOT / "locales/ar.json"
if not arabic_file.exists():
    errors.append("Arabic locale file is missing")
else:
    ar = json.loads(arabic_file.read_text(encoding="utf-8"))
    ar_ui = ar.get("ui", {})
    ar_phrase = "فن يحمل حكاية."
    ar_text = " ".join([
        str(canonical.get("ar", {}).get("heroTitle", "")),
        str(ar_ui.get("heroTitle", "")),
        str(ar_ui.get("tagline", "")),
    ])
    plain_ar_text = " ".join(re.sub(r"<[^>]+>", " ", ar_text).split())
    if ar_phrase not in plain_ar_text:
        errors.append("Arabic required phrase 'فن يحمل حكاية.' not found in canonical or locale UI copy")
    if "فن يحمل حتة." in source or "فن يحمل حتة." in json.dumps(ar, ensure_ascii=False):
        errors.append("Incorrect Arabic phrase 'فن يحمل حتة.' detected")
    if ar.get("_ui_reviewed") is not True or ar.get("_ui_translation_status") != "editorially-reviewed":
        errors.append("Arabic UI is not marked as editorially reviewed")
    if not any(entry.get("code") == "ar" and entry.get("rtl") is True for entry in registry.get("languages", [])):
        errors.append("Arabic is not registered as an RTL language")
    if 'document.documentElement.dir=rtl?"rtl":"ltr"' not in source:
        errors.append("Homepage language script does not set document direction")
    if 'document.documentElement.dir=rtl?"rtl":"ltr"' not in landing_source:
        errors.append("Product-page language script does not set document direction")
    if "available!==false" not in source or "available!==false" not in landing_source:
        errors.append("Homepage or product-page language selector does not filter unavailable locales")
    if "hogDefaultHtml" not in landing_source:
        errors.append("Product-page language switcher does not restore original content when changing languages")

ar_product_status={"editorially-reviewed":0,"editorial-draft-ai-assisted":0,"unmarked-or-machine":0}
if arabic_file.exists():
    ar_data=json.loads(arabic_file.read_text(encoding="utf-8"))
    for item in ar_data.get("products",{}).values():
        status=item.get("_translation_status")
        if status in ("editorially-reviewed","editorial-draft-ai-assisted"):
            ar_product_status[status]+=1
        else:
            ar_product_status["unmarked-or-machine"]+=1

print("LOCALE QUALITY SUMMARY")
print(f"Registered non-English languages: {counts['registered']}")
print(f"Locale files present: {counts['files']}")
print(f"UI review status: reviewed={counts['reviewed']}, machine-unreviewed={counts['machine']}, unmarked={counts['unmarked']}")
print(f"Published products in catalogue: {len(expected_products)}")
print("Arabic product copy status: " + ", ".join(f"{k}={v}" for k,v in ar_product_status.items()))
if rtl_missing:
    print("RTL locales without files: " + ", ".join(rtl_missing))
for warning in warnings:
    print("WARNING: " + warning)
for error in errors:
    print("ERROR: " + error)
if errors:
    print(f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
    sys.exit(1)
print(f"PASSED: no structural locale errors; {len(warnings)} warning(s) require localization/editorial follow-up.")
