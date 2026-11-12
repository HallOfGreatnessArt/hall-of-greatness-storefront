#!/usr/bin/env python3
"""Free offline localization using Argos Translate with MADLAD-400 fallback.

Argos handles installed direct language pairs; MADLAD-400 fills unsupported pairs.
Both run locally on CPU with open-source models and no paid translation API.
New/changed products are translated automatically during storefront builds.
"""
import argparse, hashlib, json, re
from pathlib import Path

import argostranslate.package
import argostranslate.translate
from free_translation import has_fallback_engine, translate_texts

ROOT=Path(__file__).resolve().parents[1]
REG=json.loads((ROOT/"locales/languages.json").read_text(encoding="utf-8"))["languages"]
CAT=json.loads((ROOT/"catalog-data.json").read_text(encoding="utf-8"))
source=(ROOT/"assets/i18n.js").read_text(encoding="utf-8")
match=re.search(r"const M=(\{[\s\S]*?\});\nconst map=",source)
if not match: raise SystemExit("Could not locate canonical UI dictionary.")
ui=json.loads(match.group(1))["en"]
landing_ui=json.loads((ROOT/"assets/landing-copy.json").read_text(encoding="utf-8"))
detail_labels={
    "files_included":"Files included",
    "product_type":"Product type",
    "delivery":"Delivery",
    "physical_item":"Physical item",
    "printing":"Printing",
    "usage":"Usage",
    "bundle_item_count":"Items in bundle",
}

# Argos package language codes are not always identical to BCP-47 storefront tags.
CODE_MAP={"zh-CN":"zh","pt":"pt","fa":"fa","he":"he","ar":"ar"}
def digest(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def save_locale(path, data):
    """Atomically checkpoint one locale so an interrupted stage can resume."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    temporary.replace(path)


def selected_language_codes():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-index", type=int, default=0)
    parser.add_argument("--batch-count", type=int, default=1)
    args = parser.parse_args()
    if args.batch_count < 1 or not 0 <= args.batch_index < args.batch_count:
        parser.error("--batch-index must be within --batch-count")
    codes = [item["code"] for item in REG if item.get("code") != "en"]
    size = (len(codes) + args.batch_count - 1) // args.batch_count
    start = args.batch_index * size
    return set(codes[start:start + size])

print("Refreshing the free Argos Translate model index...")
argostranslate.package.update_package_index()
available=argostranslate.package.get_available_packages()
installed_codes={x.code for x in argostranslate.translate.get_installed_languages()}
translation_cache={}

def get_translator(target):
    target=CODE_MAP.get(target,target)
    if target in translation_cache: return translation_cache[target]
    installed=argostranslate.translate.get_installed_languages()
    src=next((x for x in installed if x.code=="en"),None)
    dst=next((x for x in installed if x.code==target),None)
    if src and dst:
        translator=src.get_translation(dst)
        if translator:
            translation_cache[target]=translator
            return translator
    package=next((p for p in available if p.from_code=="en" and p.to_code==target),None)
    if not package:
        translation_cache[target]=None
        print(f"NO MODEL: en -> {target}; keeping English fallback.")
        return None
    try:
        print(f"Installing free Argos model en -> {target}...")
        argostranslate.package.install_from_path(package.download())
        installed=argostranslate.translate.get_installed_languages()
        src=next(x for x in installed if x.code=="en")
        dst=next(x for x in installed if x.code==target)
        translation_cache[target]=src.get_translation(dst)
        return translation_cache[target]
    except Exception as exc:
        print(f"MODEL ERROR {target}: {exc}; keeping English fallback.")
        translation_cache[target]=None
        return None

def translate_many(values, target):
    translator=get_translator(target)
    if translator is None and not has_fallback_engine():
        print(f"NO FREE MODEL AVAILABLE: {target}; retaining English fallback.")
        return None
    # Keep the Argos-first order while batching all unsupported pairs through MADLAD.
    result=translate_texts([str(value) for value in values], target, translator)
    if result is None:
        print(f"All free translation engines failed for {target}; retaining previous locale data.")
    return result

selected_codes = selected_language_codes()
print(f"Selected locale batch: {sorted(selected_codes)}", flush=True)

for lang in REG:
    code=lang["code"]
    if code not in selected_codes: continue
    target=CODE_MAP.get(code,code)
    path=ROOT/"locales"/(code+".json")
    old=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    ui_hash=digest(ui)
    products=old.setdefault("products",{})
    pending=[]
    for p in CAT["products"]:
        if not p.get("published"): continue
        key=p["permalink"]
        fields={k:p.get(k) for k in ("summary","full_description","category") if p.get(k)}
        fields["product_details"]=p.get("product_details") or {}
        if products.get(key,{}).get("_source_hash")!=digest(fields):
            pending.append((p,key,fields))
    reviewed_ui = old.get("_ui_reviewed") is True and bool(old.get("ui"))
    landing_hash=digest(landing_ui)
    detail_labels_hash=digest(detail_labels)
    needs_detail_labels=old.get("_product_detail_labels_source_hash")!=detail_labels_hash
    reviewed_landing = old.get("_landing_ui_reviewed") is True and bool(old.get("landing_ui"))
    needs_landing = old.get("_landing_ui_source_hash") != landing_hash and not reviewed_landing
    if reviewed_landing and old.get("_landing_ui_source_hash") != landing_hash:
        print(f"REVIEW REQUIRED: {code} landing-page copy changed; preserving reviewed translation.")
    if reviewed_ui and old.get("_ui_source_hash") != ui_hash:
        print(f"REVIEW REQUIRED: {code} source UI changed; preserving reviewed translation.")
    needs_ui=old.get("_ui_source_hash")!=ui_hash and not reviewed_ui
    if not needs_ui and not pending and not needs_landing and not needs_detail_labels:
        print(f"Up to date: {code}; no model installation needed.")
        continue
    translator=get_translator(target)
    if translator is None and not has_fallback_engine():
        print(f"NO FREE MODEL AVAILABLE: {code}; keeping English fallback.")
        continue
    if needs_ui:
        keys=list(ui)
        raw=[re.sub(r"<[^>]+>","",ui[k]) if "<" in ui[k] else ui[k] for k in keys]
        vals=translate_many(raw,code)
        if vals is None: continue
        translated=dict(zip(keys,vals))
        if "<em>" in ui.get("heroTitle",""):
            translated["heroTitle"]="<em>"+translated["heroTitle"]+"</em>"
        old["ui"]=translated
        old["_ui_source_hash"]=ui_hash
        old["_ui_translation_status"]="machine-generated-unreviewed"
        save_locale(path, old)
    if reviewed_ui:
        old["_ui_translation_status"]="editorially-reviewed"
    if needs_landing:
        keys=list(landing_ui)
        vals=translate_many([landing_ui[k] for k in keys],code)
        if vals is not None:
            old["landing_ui"]=dict(zip(keys,vals))
            old["_landing_ui_source_hash"]=landing_hash
            old["_landing_ui_translation_status"]="machine-generated-unreviewed"
            save_locale(path, old)
    elif reviewed_landing:
        old["_landing_ui_translation_status"]="editorially-reviewed"
    if needs_detail_labels:
        label_keys=list(detail_labels)
        label_values=translate_many([detail_labels[key] for key in label_keys],code)
        if label_values is not None:
            old["product_detail_labels"]=dict(zip(label_keys,label_values))
            old["_product_detail_labels_source_hash"]=detail_labels_hash
            old["_product_detail_labels_translation_status"]="machine-generated-unreviewed"
            save_locale(path, old)
    for p,key,fields in pending:
        source_hash=digest(fields)
        flat=[]; flat_keys=[]
        for k,v in fields.items():
            if k=="product_details":
                for dk,dv in v.items():
                    if dv: flat_keys.append(("detail",dk)); flat.append(str(dv))
            elif v:
                flat_keys.append((k,None)); flat.append(str(v))
        vals=translate_many(flat,code)
        if vals is None: continue
        item={}
        for (k,dk),value in zip(flat_keys,vals):
            if k=="detail": item.setdefault("product_details",{})[dk]=value
            else: item[k]=value
        item["_source_hash"]=source_hash
        products[key]=item
        save_locale(path, old)
    save_locale(path, old)
    print(f"Localized {code}: {len(products)} products", flush=True)
