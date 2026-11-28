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
EBOOK_COPY=json.loads((ROOT/"ebook-copy.json").read_text(encoding="utf-8"))
source=(ROOT/"assets/i18n.js").read_text(encoding="utf-8")
match=re.search(r"const M=(\{[\s\S]*?\});\nconst map=",source)
if not match: raise SystemExit("Could not locate canonical UI dictionary.")
UI_DICTIONARY=json.loads(match.group(1))
ui=UI_DICTIONARY["en"]

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
    existing_ui=old.setdefault("ui",{})
    # Reuse the exact hand-authored gallery dictionary wherever it exists.
    # For all other locales, add only missing keys through the same Argos engine;
    # never regenerate or overwrite the gallery's existing product/UI translations.
    manual_ui=UI_DICTIONARY.get(code,{})
    for key in ui:
        if key not in existing_ui and key in manual_ui:
            existing_ui[key]=manual_ui[key]
    reviewed_ui = old.get("_ui_reviewed") is True and bool(existing_ui)
    if reviewed_ui and old.get("_ui_source_hash") != ui_hash:
        print(f"REVIEW REQUIRED: {code} source UI changed; preserving reviewed translation.")
    needs_ui=not bool(existing_ui)
    fallback_ui_keys=set(old.get("_ui_fallback_keys",[]))
    missing_ui_keys=[key for key in ui if key not in existing_ui or key in fallback_ui_keys]
    needs_missing_ui=bool(missing_ui_keys)
    needs_ebooks = any(
        not isinstance(old.get("ebooks",{}).get(book_key),dict)
        or old.get("ebooks",{}).get(book_key,{}).get("_source_hash") != digest(copy.get("en",{}))
        or not isinstance(old.get("ebooks",{}).get(book_key,{}).get("title"),str)
        or len(old.get("ebooks",{}).get(book_key,{}).get("title","").strip()) < 3
        or not isinstance(old.get("ebooks",{}).get(book_key,{}).get("overview"),str)
        or len(old.get("ebooks",{}).get(book_key,{}).get("overview","").strip()) < 80
        or any(
            not isinstance(old.get("ebooks",{}).get(book_key,{}).get(field),list)
            or len(old.get("ebooks",{}).get(book_key,{}).get(field,[])) != len(copy.get("en",{}).get(field,[]))
            or any(not isinstance(part,str) or len(part.strip()) < 10 for part in old.get("ebooks",{}).get(book_key,{}).get(field,[]))
            for field in ("explore","takeaways")
        )
        for book_key,copy in EBOOK_COPY.items()
    )
    needs_ar_titles = code=="ar" and any(
        p.get("published") and p.get("permalink") and
        not str(products.get(p["permalink"],{}).get("title_ar","")).strip()
        for p in CAT["products"]
    )
    if not needs_ui and not needs_missing_ui and not pending and not needs_ebooks and not needs_ar_titles:
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
                # Preserve all existing gallery strings and add only missing keys.
                existing_ui.update(translated)
                old["ui"]=existing_ui
                if reviewed_ui:
                    old["_ui_translation_status"]="editorially-reviewed-with-new-machine-keys"
                else:
                    old["_ui_translation_status"]=old.get("_ui_translation_status","machine-generated-unreviewed")
            old["_ui_fallback_keys"]=sorted(fallback_ui_keys.difference(keys))
        else:
            # A model may be installed but fail on individual UI strings.
            # Keep the selector structurally safe using explicitly labelled
            # English fallback keys; this locale remains unavailable for pages.
            still_missing=[key for key in ui if key not in existing_ui]
            existing_ui.update({key:ui[key] for key in still_missing})
            old["ui"]=existing_ui
            old["_ui_fallback_keys"]=sorted(set(old.get("_ui_fallback_keys",[])).union(still_missing))
            old["_ui_translation_status"]="english-fallback-incomplete"
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
        products[key]=item

    # Translate curated e-book copy field-by-field. Never replace existing
    # editorial text: only fill missing/unsafe fields, preserving every approved
    # string and list item even when the source hash has changed.
    ebook_translations=old.setdefault("ebooks",{})
    for book_key, source_copy in EBOOK_COPY.items():
        source_english=source_copy.get("en",{})
        if not source_english:
            continue
        source_hash=digest(source_english)
        existing=dict(ebook_translations.get(book_key,{}) or {})
        if code=="ar" and isinstance(source_copy.get("ar"),dict):
            # The Arabic book copy is already curated in the editorial source.
            # Reuse it verbatim rather than producing a second machine translation.
            for field,value in source_copy["ar"].items():
                if field not in existing or not existing.get(field):
                    existing[field]=value
            existing["_source_hash"]=source_hash
            existing["_translation_status"]="editorially-reviewed"
            ebook_translations[book_key]=existing
            print(f"Reused curated Arabic e-book copy {book_key}.")
            continue
        status=existing.get("_translation_status","")
        editorial=status in ("editorially-reviewed","editorial-draft-ai-assisted")
        pending_paths=[]
        pending_values=[]
        for field,value in source_english.items():
            if isinstance(value,list):
                current=existing.get(field)
                current=list(current) if isinstance(current,list) else []
                if len(current)<len(value):
                    current.extend([""]*(len(value)-len(current)))
                for index,source_value in enumerate(value):
                    current_value=current[index]
                    valid=isinstance(current_value,str) and len(current_value.strip())>=10 and not re.search(r"(.)\1{5,}",current_value,re.I)
                    if not valid and isinstance(source_value,str) and source_value.strip():
                        pending_paths.append((field,index))
                        pending_values.append(source_value)
                existing[field]=current
            elif isinstance(value,str) and value.strip():
                current_value=existing.get(field)
                minimum=3 if field=="title" else (30 if field=="overview" else 8)
                valid=isinstance(current_value,str) and len(current_value.strip())>=minimum and not re.search(r"(.)\1{5,}",current_value,re.I)
                if not valid:
                    pending_paths.append((field,None))
                    pending_values.append(value)
        if pending_values:
            translated_values=translate_many(pending_values,code)
            if translated_values is not None and len(translated_values)==len(pending_paths):
                for (field,index),translated_value in zip(pending_paths,translated_values):
                    if not isinstance(translated_value,str) or not translated_value.strip():
                        continue
                    if index is None:
                        # Replace invalid machine copy, but never overwrite
                        # editorially prepared content.
                        if not editorial:
                            existing[field]=translated_value.strip()
                        elif not str(existing.get(field,"")).strip():
                            existing[field]=translated_value.strip()
                    else:
                        values=existing.setdefault(field,[])
                        while len(values)<=index: values.append("")
                        if not editorial or not str(values[index]).strip():
                            values[index]=translated_value.strip()
                if not editorial:
                    existing["_translation_status"]="machine-generated-unreviewed"
        existing["_source_hash"]=source_hash
        ebook_translations[book_key]=existing
        print(f"Checked curated e-book translation {code}/{book_key}; preserved existing editorial fields.")
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


# Product-page availability is stricter than gallery registration. A locale is
# exposed only when every required page field is present, current, and safe.
def safe_text(value, minimum=1, maximum=12000):
    return (isinstance(value,str) and minimum <= len(value.strip()) <= maximum
            and not re.search(r"(.)\1{5,}",value,re.I)
            and not re.search(r"add to wishlist|powered by gumroad|more from this creator|explore our collection",value,re.I))

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
    reasons=[]
    if path.exists():
        try:
            localized=json.loads(path.read_text(encoding='utf-8'))
            localized_ui=localized.get('ui',{})
            if not isinstance(localized_ui,dict) or not expected_ui_keys.issubset(set(localized_ui)):
                reasons.append('incomplete UI')
            if localized.get('_ui_fallback_keys'):
                reasons.append('English UI fallback present')
            elif any(not safe_text(localized_ui.get(key),1,2000) for key in expected_ui_keys):
                reasons.append('unsafe/empty UI')
            localized_products=localized.get('products',{})
            if not expected_product_keys.issubset(set(localized_products)):
                reasons.append('incomplete product catalogue')
            for product in CAT['products']:
                if not product.get('published') or not product.get('permalink'):
                    continue
                item=localized_products.get(product['permalink'],{})
                fields={k:product.get(k) for k in ('summary','full_description','category') if product.get(k)}
                fields['product_details']=product.get('product_details') or {}
                if item.get('_source_hash')!=digest(fields):
                    reasons.append('stale product source')
                    break
                if any(not safe_text(item.get(field),20 if field in ('summary','full_description') else 1)
                       for field in ('summary','full_description','category')):
                    reasons.append('unsafe/incomplete product copy')
                    break
            localized_ebooks=localized.get('ebooks',{})
            for book_key,copy in EBOOK_COPY.items():
                item=localized_ebooks.get(book_key,{})
                if item.get('_source_hash')!=digest(copy.get('en',{})):
                    reasons.append('stale/missing curated e-book source')
                    break
                if not safe_text(item.get('title'),3,300) or not safe_text(item.get('overview'),80,12000):
                    reasons.append('incomplete curated e-book title/overview')
                    break
                for field in ('explore','takeaways'):
                    source_list=copy.get('en',{}).get(field,[])
                    values=item.get(field,[])
                    if not isinstance(values,list) or len(values)!=len(source_list) or any(not safe_text(x,10,2000) for x in values):
                        reasons.append('incomplete curated e-book lists')
                        break
                if reasons:
                    break
            complete=not reasons
        except (UnicodeError,json.JSONDecodeError,TypeError):
            complete=False
            reasons.append('invalid locale data')
    lang['available']=complete
    lang['availability_note']='complete, current product-page translations' if complete else 'not offered on product pages: '+', '.join(dict.fromkeys(reasons or ['translation file/model unavailable']))
REGISTRY_DATA['provider']='Argos Translate (open-source, offline models)'
REGISTRY_DATA['translation_mode']='Free offline translation; product pages expose only complete, current, safe locales. Existing editorial translations are preserved; unsupported or incomplete locales are hidden rather than misrepresented.'
REGISTRY_PATH.write_text(json.dumps(REGISTRY_DATA,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Updated product-page availability flags using full UI, product, and curated e-book completeness checks.')
