#!/usr/bin/env python3
"""Create cached UI and product translations for every configured storefront language.

Requires GOOGLE_TRANSLATE_API_KEY. Artwork titles and brand names remain unchanged.
"""
import hashlib, json, os, re, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REG=json.loads((ROOT/"locales/languages.json").read_text(encoding="utf-8"))["languages"]
CAT=json.loads((ROOT/"catalog-data.json").read_text(encoding="utf-8"))
API=os.environ.get("GOOGLE_TRANSLATE_API_KEY","").strip()
if not API:
    raise SystemExit("GOOGLE_TRANSLATE_API_KEY is not configured; localization generation skipped.")
# Read the canonical English UI dictionary from the existing frontend bundle.
source=(ROOT/"assets/i18n.js").read_text(encoding="utf-8")
match=re.search(r"const M=(\{[\s\S]*?\});\nconst map=",source)
if not match: raise SystemExit("Could not locate the canonical UI translation dictionary.")
ui=json.loads(match.group(1))["en"]

def translate_many(values, target):
    vals=[str(v) for v in values]
    if not vals: return []
    # Google Cloud Translation v2 accepts a q array.
    data=urllib.parse.urlencode([("q",v) for v in vals]+[("target",target),("format","text")]).encode()
    req=urllib.request.Request("https://translation.googleapis.com/language/translate/v2?key="+urllib.parse.quote(API),data=data,headers={"Content-Type":"application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req,timeout=45) as response:
        payload=json.loads(response.read().decode("utf-8"))
    return [x["translatedText"] for x in payload["data"]["translations"]]

def digest(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

for lang in REG:
    code=lang["code"]
    if code=="en": continue
    path=ROOT/"locales"/(code+".json")
    old=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    ui_hash=digest(ui)
    if old.get("_ui_source_hash")!=ui_hash:
        keys=list(ui)
        vals=translate_many([re.sub(r"<[^>]+>","",ui[k]) if "<" in ui[k] else ui[k] for k in keys],code)
        # Restore the two intentional emphasis tags in the hero headline.
        translated=dict(zip(keys,vals))
        if "<em>" in ui.get("heroTitle",""):
            translated["heroTitle"]="<em>"+translated["heroTitle"]+"</em>"
        old["ui"]=translated
        old["_ui_source_hash"]=ui_hash
    products=old.setdefault("products",{})
    for p in CAT["products"]:
        if not p.get("published"): continue
        key=p["permalink"]
        fields={k:p.get(k) for k in ("summary","full_description","category") if p.get(k)}
        details=p.get("product_details") or {}
        fields["product_details"]=details
        source_hash=digest(fields)
        cached=products.get(key,{})
        if cached.get("_source_hash")==source_hash: continue
        flat=[]
        flat_keys=[]
        for k,v in fields.items():
            if k=="product_details":
                for dk,dv in v.items():
                    if dv: flat_keys.append(("detail",dk)); flat.append(str(dv))
            else:
                flat_keys.append((k,None)); flat.append(str(v))
        translated=translate_many(flat,code)
        item={}
        for (k,dk),value in zip(flat_keys,translated):
            if k=="detail": item.setdefault("product_details",{})[dk]=value
            else: item[k]=value
        item["_source_hash"]=source_hash
        products[key]=item
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(old,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Localized {code}: {len(products)} products")
