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
match = re.search(r"const M=(\{[\s\S]*?\});\nconst map=", source)
if not match:
    raise SystemExit("ERROR: canonical UI dictionary not found in assets/i18n.js")
canonical = json.loads(match.group(1))
english = canonical.get("en", {})
expected_keys = set(english)
catalog = json.loads((ROOT / "catalog-data.json").read_text(encoding="utf-8"))
published = [p for p in catalog.get("products", []) if p.get("published")]
expected_products = {p.get("permalink") for p in published if p.get("permalink")}

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
    for slug, item in products.items():
        if not isinstance(item, dict):
            errors.append(f"{code}/{slug}: product translation is not an object")
            continue
        for field in ("summary", "full_description"):
            value = item.get(field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                errors.append(f"{code}/{slug}: empty or invalid {field}")
            if isinstance(value, str):
                if "\ufffd" in value:
                    errors.append(f"{code}/{slug}: Unicode replacement character in {field}")
                if re.search(r"(?:Ã.|Â.|Ø[ء-ي]|Ù[ء-ي])", value):
                    warnings.append(f"{code}/{slug}: possible mojibake in {field}")
                entities = re.findall(r"&(?:quot|apos|amp|lt|gt);", value)
                if entities:
                    warnings.append(f"{code}/{slug}: {len(entities)} HTML entities remain in {field}; renderer must decode before escaping")

# The Arabic hero phrase is a release-critical copy requirement.
arabic_hero = re.sub(r"<[^>]+>", "", str(canonical.get("ar", {}).get("heroTitle", "")))
arabic_file = ROOT / "locales/ar.json"
if not arabic_file.exists():
    errors.append("Arabic locale file is missing")
else:
    ar = json.loads(arabic_file.read_text(encoding="utf-8"))
    ar_ui = ar.get("ui", {})
    ar_phrase = "فن يحمل حكاية."
    ar_text = " ".join([arabic_hero, str(ar_ui.get("heroTitle", "")), str(ar_ui.get("tagline", ""))])
    if ar_phrase not in re.sub(r"<[^>]+>", "", ar_text):
        errors.append("Arabic required phrase 'فن يحمل حكاية.' not found in canonical or locale UI copy")
    if "فن يحمل حتة." in source or "فن يحمل حتة." in json.dumps(ar, ensure_ascii=False):
        errors.append("Incorrect Arabic phrase 'فن يحمل حتة.' detected")
    if ar.get("_ui_reviewed") is not True or ar.get("_ui_translation_status") != "editorially-reviewed":
        errors.append("Arabic UI is not marked as editorially reviewed")

print("LOCALE QUALITY SUMMARY")
print(f"Registered non-English languages: {counts['registered']}")
print(f"Locale files present: {counts['files']}")
print(f"UI review status: reviewed={counts['reviewed']}, machine-unreviewed={counts['machine']}, unmarked={counts['unmarked']}")
print(f"Published products in catalogue: {len(expected_products)}")
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
