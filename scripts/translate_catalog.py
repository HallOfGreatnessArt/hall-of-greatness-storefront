#!/usr/bin/env python3
"""Free offline localization using open-source Argos Translate models.

Only language pairs present in the upstream Argos package index are translated.
Other registered languages safely retain English fallback until a model exists.
New/changed products are translated automatically during storefront builds.
"""
import hashlib, json, re
from pathlib import Path

import argostranslate.package
import argostranslate.translate

ROOT=Path(__file__).resolve().parents[1]
REGISTRY_PATH=ROOT/"locales/languages.json"
REGISTRY_DATA=json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
REG=REGISTRY_DATA["languages"]
CAT=json.loads((ROOT/"catalog-data.json").read_text(encoding="utf-8"))
source=(ROOT/"assets/i18n.js").read_text(encoding="utf-8")
match=re.search(r"const M=(\{[\s\S]*?\});\nconst map=",source)
if not match: raise SystemExit("Could not locate canonical UI dictionary.")
ui=json.loads(match.group(1))["en"]

# Argos package language codes are not always identical to BCP-47 storefront tags.
CODE_MAP={"zh-CN":"zh","zh-TW":"zh","pt":"pt","fa":"fa","he":"he","ar":"ar"}
def digest(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

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
    if translator is None: return None
    result=[]
    for value in values:
        # Argos splits longer content into sentence-sized segments internally.
        try: result.append(translator.translate(str(value)))
        except Exception as exc:
            print(f"Translation failed for {target}: {exc}")
            return None
    return result

for lang in REG:
    code=lang["code"]
    if code=="en": continue
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
        existing=products.get(key,{})
        existing_status=existing.get("_translation_status")
        if existing_status in ("editorial-draft-ai-assisted","editorially-reviewed"):
            if existing.get("_source_hash")!=digest(fields):
                print(f"REVIEW REQUIRED: {code}/{key} source changed; preserving editorial copy.")
            continue
        if existing.get("_source_hash")!=digest(fields):
            pending.append((p,key,fields))
    reviewed_ui = old.get("_ui_reviewed") is True and bool(old.get("ui"))
    if reviewed_ui and old.get("_ui_source_hash") != ui_hash:
        print(f"REVIEW REQUIRED: {code} source UI changed; preserving reviewed translation.")
    needs_ui=old.get("_ui_source_hash")!=ui_hash and not reviewed_ui
    existing_ui=old.setdefault("ui",{})
    fallback_ui_keys=set(old.get("_ui_fallback_keys",[]))
    missing_ui_keys=[key for key in ui if key not in existing_ui or key in fallback_ui_keys]
    needs_missing_ui=bool(missing_ui_keys)
    needs_ar_titles = code=="ar" and any(
        p.get("published") and p.get("permalink") and
        not str(products.get(p["permalink"],{}).get("title_ar","")).strip()
        for p in CAT["products"]
    )
    if not needs_ui and not needs_missing_ui and not pending and not needs_ar_titles:
        print(f"Up to date: {code}; no model installation needed.")
        continue
    translator=get_translator(target)
    if translator is None:
        if needs_missing_ui:
            existing_ui.update({key: ui[key] for key in missing_ui_keys})
            old["ui"]=existing_ui
            old["_ui_fallback_keys"]=sorted(fallback_ui_keys.union(missing_ui_keys))
            old["_ui_translation_status"]="english-fallback-incomplete"
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(old,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            print(f"English fallback added for unsupported UI keys: {code} ({len(missing_ui_keys)} key(s)); locale remains unavailable.")
        continue
    if needs_ui or needs_missing_ui:
        keys=list(ui) if needs_ui else missing_ui_keys
        raw=[re.sub(r"<[^>]+>","",ui[k]) if "<" in ui[k] else ui[k] for k in keys]
        vals=translate_many(raw,code)
        if vals is not None:
            translated=dict(zip(keys,vals))
            if "heroTitle" in translated and "<em>" in ui.get("heroTitle",""):
                translated["heroTitle"]="<em>"+translated["heroTitle"]+"</em>"
            if needs_ui:
                old["ui"]=translated
                old["_ui_source_hash"]=ui_hash
                old["_ui_translation_status"]="machine-generated-unreviewed"
            else:
                # Preserve editorially reviewed strings; add only newly introduced
                # keys so the expanded navigation and three sections stay translated.
                existing_ui.update(translated)
                old["ui"]=existing_ui
                old["_ui_translation_status"]="editorially-reviewed-with-new-machine-keys"
            old["_ui_fallback_keys"]=sorted(fallback_ui_keys.difference(keys))
    if reviewed_ui and not needs_missing_ui:
        old["_ui_translation_status"]="editorially-reviewed"
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
        item["_translation_status"]="machine-generated-unreviewed"
        products[key]=item

    # Arabic product cards require a localized display title in addition to
    # the translated description. Generate missing titles for newly imported
    # products while preserving any existing editorially prepared title.
    if code=="ar":
        for p in CAT["products"]:
            if not p.get("published") or not p.get("permalink"):
                continue
            item=products.setdefault(p["permalink"],{})
            if str(item.get("title_ar","")).strip():
                continue
            title_values=translate_many([p.get("name","")],code)
            if title_values and title_values[0].strip():
                item["title_ar"]=title_values[0].strip()
                item["_title_translation_status"]="machine-generated-unreviewed"

    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(old,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Localized {code}: {len(products)} products")


# Only expose languages with complete UI and product translation files.
# Unsupported languages remain documented in the registry but are hidden from the selector.
expected_product_keys={p['permalink'] for p in CAT['products'] if p.get('published') and p.get('permalink')}
expected_ui_keys=set(ui)
for lang in REG:
    code=lang['code']
    if code=='en':
        lang['available']=True
        lang['availability_note']='source language'
        continue
    path=ROOT/'locales'/(code+'.json')
    complete=False
    if path.exists():
        try:
            localized=json.loads(path.read_text(encoding='utf-8'))
            localized_ui=localized.get('ui',{})
            localized_products=localized.get('products',{})
            products_current=True
            for product in CAT["products"]:
                if not product.get("published") or not product.get("permalink"):
                    continue
                fields={k:product.get(k) for k in ("summary","full_description","category") if product.get(k)}
                fields["product_details"]=product.get("product_details") or {}
                item=localized_products.get(product["permalink"],{})
                if item.get("_source_hash")!=digest(fields):
                    products_current=False
                    break
            # Expose a locale only after both its interface and every published
            # product translation have explicit human editorial approval.
            ui_approved=(localized.get("_ui_reviewed") is True and
                         localized.get("_ui_translation_status")=="editorially-reviewed")
            products_approved=all(
                localized_products.get(product["permalink"],{}).get("_translation_status")=="editorially-reviewed"
                for product in CAT["products"] if product.get("published") and product.get("permalink")
            )
            complete=(expected_ui_keys.issubset(set(localized_ui)) and
                      not localized.get("_ui_fallback_keys") and
                      expected_product_keys.issubset(set(localized_products)) and
                      products_current and ui_approved and products_approved)
        except (UnicodeError,json.JSONDecodeError):
            complete=False
    lang['available']=complete
    lang['availability_note']='complete UI and product translations' if complete else 'translation file/model unavailable or incomplete'
REGISTRY_DATA['provider']='Argos Translate (open-source, offline models)'
REGISTRY_DATA['translation_mode']='Free offline translation during GitHub Actions builds; language availability depends on installed model pairs; incomplete languages are hidden from the storefront selector.'
REGISTRY_PATH.write_text(json.dumps(REGISTRY_DATA,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Updated language availability flags; incomplete locales remain hidden until complete.')
