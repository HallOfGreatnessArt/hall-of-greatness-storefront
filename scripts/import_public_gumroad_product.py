#!/usr/bin/env python3
"""Import one public Gumroad product into a test storefront catalogue without OAuth."""
from __future__ import annotations
import argparse, html, json, re, sys, urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
STORE_HOST = "alshayebemad.gumroad.com"

class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.meta={}; self.title_parts=[]; self.in_title=False; self.json_ld=[]; self.in_json=False; self.script=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag.lower()=="meta":
            k=a.get("property") or a.get("name") or a.get("itemprop"); v=a.get("content")
            if k and v: self.meta[k.lower()]=html.unescape(v.strip())
        elif tag.lower()=="title": self.in_title=True
        elif tag.lower()=="script" and a.get("type","").lower()=="application/ld+json":
            self.in_json=True; self.script=[]
    def handle_endtag(self, tag):
        if tag.lower()=="title": self.in_title=False
        elif tag.lower()=="script" and self.in_json:
            self.json_ld.append("".join(self.script)); self.in_json=False; self.script=[]
    def handle_data(self, data):
        if self.in_title: self.title_parts.append(data)
        if self.in_json: self.script.append(data)

def walk(v):
    if isinstance(v,dict):
        yield v
        for x in v.values(): yield from walk(x)
    elif isinstance(v,list):
        for x in v: yield from walk(x)

def schema_product(p):
    for raw in p.json_ld:
        try: parsed=json.loads(raw)
        except json.JSONDecodeError: continue
        for obj in walk(parsed):
            t=obj.get("@type",[]); t=[t] if isinstance(t,str) else t
            if any(str(x).lower()=="product" for x in t): return obj
    return {}

def slugify(s): return re.sub(r"[^a-z0-9]+","-",s.lower()).strip("-") or "new-artwork"

def category_for(name, desc):
    s=f"{name} {desc}".lower()
    if any(w in s for w in ("egypt","egyptian","nile","coptic","roman","heritage","pharaoh")): return "Heritage"
    if any(w in s for w in ("humanity","compassion","generation","child","earth","hands","hope","legacy","tree")): return "Humanity"
    if any(w in s for w in ("elegance","serenity","peace","golden","luxury","celestial","garden","grace")): return "Elegance"
    return "Global"

def fetch(url):
    u=urlparse(url)
    if u.scheme!="https" or u.hostname!=STORE_HOST or not u.path.startswith("/l/"):
        raise ValueError("Only public product URLs on the approved Gumroad storefront are allowed")
    req=urllib.request.Request(url,headers={"User-Agent":"HALL-OF-GREATNESS-public-catalog-import/1.0"})
    with urllib.request.urlopen(req,timeout=30) as r:
        final=r.geturl(); body=r.read(8_000_000).decode("utf-8",errors="replace")
    if urlparse(final).hostname!=STORE_HOST: raise ValueError("Redirect outside approved Gumroad storefront")
    p=MetadataParser(); p.feed(body)
    return p,final

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--url",required=True); ap.add_argument("--catalog",default="catalog-data.json")
    args=ap.parse_args()
    p,final=fetch(args.url); m=p.meta; schema=schema_product(p)
    name=(m.get("og:title") or m.get("twitter:title") or schema.get("name") or "".join(p.title_parts)).strip()
    desc=(m.get("og:description") or m.get("description") or schema.get("description") or "").strip()
    image=m.get("og:image") or m.get("twitter:image")
    if not image:
        im=schema.get("image"); image=im if isinstance(im,str) else (im[0] if isinstance(im,list) and im else "")
    match=re.search(r"/l/([^/?#]+)",final)
    permalink=m.get("product:retailer_item_id") or (match.group(1) if match else "")
    raw_price=m.get("product:price:amount"); currency=m.get("product:price:currency","USD").upper()
    if not raw_price and isinstance(schema.get("offers"),dict):
        raw_price=str(schema["offers"].get("price","")); currency=str(schema["offers"].get("priceCurrency",currency)).upper()
    missing=[k for k,v in {"name":name,"description":desc,"image":image,"product id":permalink,"price":raw_price}.items() if not v]
    if missing: raise ValueError("Public page lacks required fields: "+", ".join(missing))
    if currency!="USD": raise ValueError("Expected USD, got "+currency)
    data=json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    existing=next((x for x in data["products"] if x.get("permalink")==permalink),None)
    if existing:
        print(json.dumps({"status":"already_present","product":existing},ensure_ascii=False,indent=2)); return
    slug=slugify(name); used={x.get("landing_slug") for x in data["products"]}; base=slug; n=2
    while slug in used: slug=f"{base}-{n}"; n+=1
    product={"name":name,"price_usd":float(raw_price),"url":final,"permalink":permalink,"published":True,
             "is_bundle":False,"category":category_for(name,desc),"landing_slug":slug,"cover_url":image,"summary":desc[:420]}
    data["products"].append(product); data["product_count"]=len(data["products"])
    data["source"]="Public Gumroad product page (no OAuth)"
    Path(args.catalog).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"imported","product":product},ensure_ascii=False,indent=2))
    print("PUBLIC_GUMROAD_IMPORT_OK")

if __name__=="__main__":
    try: main()
    except Exception as e:
        print("PUBLIC_GUMROAD_IMPORT_FAILED: "+str(e),file=sys.stderr); raise
