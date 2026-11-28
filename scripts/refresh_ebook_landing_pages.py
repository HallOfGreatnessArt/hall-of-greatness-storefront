#!/usr/bin/env python3
"""Build a dedicated editorial landing experience for HALL OF GREATNESS e-books."""
import html, json, os, re, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAT=json.loads((ROOT/"catalog-data.json").read_text(encoding="utf-8"))
COPY=json.loads((ROOT/"ebook-copy.json").read_text(encoding="utf-8"))
REG=json.loads((ROOT/"locales/languages.json").read_text(encoding="utf-8"))["languages"]
I18N=(ROOT/"assets/i18n.js").read_text(encoding="utf-8")
match=re.search(r"const M=(\{[\s\S]*?\});\nconst map=",I18N)
if not match: raise SystemExit("Cannot read gallery language dictionary.")
UI=json.loads(match.group(1))
def digest(obj): return __import__("hashlib").sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def safe_copy(value, minimum=20):
    if not isinstance(value,str) or len(value.strip())<minimum or len(value)>12000: return False
    if re.search(r"(.)\1{5,}",value,re.I): return False
    if re.search(r"add to wishlist|powered by gumroad|more from this creator|explore our collection|^\s*(?:share|compartir|partager|поделиться)\s*$",value,re.I|re.M): return False
    return True
LOCAL_ONLY="--local-only" in sys.argv[1:]
TOKEN=os.environ.get("GUMROAD_ACCESS_TOKEN","").strip()
if not LOCAL_ONLY and not TOKEN: raise SystemExit("GUMROAD_ACCESS_TOKEN is required.")
ENV=os.environ.copy()
OUT=ROOT/"ebook-landing-refresh-evidence"; OUT.mkdir(exist_ok=True)
PRODUCTS={p["permalink"]:p for p in CAT.get("products",[]) if p.get("published")}
EXPECTED=set(COPY)
# Verified Gumroad product IDs; permalinks are not accepted by the page-preview API.
GUMROAD_IDS={"isbsay":"rY4PnUT0tfE7HwMU1-PUhw==","qsznm":"79yd7jyexODACUFlHMtYzg==","wdwtbf":"lercTJf7VOGMGJBFzBY5sw==","ylxtub":"YUeb8io0HAxxwyJyGJcj_w==","qccitx":"K6DM7xWtceYKQMShd7D07A==","wydjxz":"qWtAJywZX6nv0urFCKus2Q=="}
missing=[k for k in EXPECTED if k not in PRODUCTS or k not in GUMROAD_IDS or not PRODUCTS[k].get("url","").startswith("https://") or not PRODUCTS[k].get("cover_url","").startswith("https://")]
if missing: raise SystemExit("Missing published ebook metadata or verified cover/URL: "+", ".join(sorted(missing)))
def esc(v): return html.escape(str(v or ""),quote=True)
def js(v): return json.dumps(v,ensure_ascii=False).replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
def render(key):
 p=PRODUCTS[key]
 translations={}
 english=dict(COPY[key]["en"]); english["ui"]=UI.get("en",{})
 translations["en"]=english
 for lang in REG:
  code=lang["code"]
  if code=="en" or not lang.get("available"): continue
  if code=="ar":
   localized=dict(COPY[key]["ar"])
   locale_path=ROOT/"locales"/"ar.json"
   locale=json.loads(locale_path.read_text(encoding="utf-8")) if locale_path.exists() else {}
   localized["ui"]=locale.get("ui") or UI.get("ar",{})
   translations[code]=localized
   continue
  locale_path=ROOT/"locales"/(code+".json")
  if not locale_path.exists(): continue
  try: locale=json.loads(locale_path.read_text(encoding="utf-8"))
  except Exception: continue
  item=(locale.get("ebooks") or {}).get(key,{})
  if item.get("_source_hash")!=digest(COPY[key]["en"]): continue
  minimums={"title":1,"subtitle":8,"strapline":8,"overview":30,"audience":30,"cta":8,"format":8,"structure":3,"delivery":8}
  if not all(safe_copy(item.get(field,""),minimums[field]) for field in minimums): continue
  if not all(isinstance(item.get(field),list) and all(safe_copy(x,10) for x in item[field]) for field in ("explore","takeaways","package")): continue
  localized={k:v for k,v in item.items() if k!="_source_hash"}
  localized["ui"]=locale.get("ui") or UI.get(code) or UI.get("en",{})
  translations[code]=localized
 languages=[{"code":"en","name":"English","rtl":False}]+[{"code":x["code"],"name":x["name"],"rtl":bool(x.get("rtl"))} for x in REG if x["code"] in translations and x["code"]!="en"]
 data={"key":key,"product":{"name":p["name"],"price":p.get("price_usd"),"url":p["url"],"cover":p["cover_url"]},"translations":translations,"languages":languages}
 return TEMPLATE.replace("__DATA__",js(data))
TEMPLATE=r"""<!doctype html><html lang="en" dir="ltr"><head>
<meta charset="utf-8">
<title>HALL OF GREATNESS Publishing — E-book</title><meta name="description" content="Bilingual editorial e-book product page from HALL OF GREATNESS Publishing."><link rel="icon" href="data:,">
<style>
:root{--bg:#10151b;--panel:#18212b;--ink:#f5f3ee;--muted:#c6cbd1;--accent:#d9b879;--line:#35414d}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font:18px/1.8 Georgia,"Times New Roman",serif}.shell{width:min(1120px,calc(100% - 44px));margin:auto}
header{min-height:76px;display:flex;align-items:center;justify-content:space-between;gap:18px;border-bottom:1px solid var(--line);flex-wrap:wrap}.brand{font:700 13px Arial,sans-serif;letter-spacing:.18em;color:var(--ink);text-decoration:none}.brand span{color:var(--accent)}.controls{display:flex;align-items:center;gap:10px}.controls label{font:14px Arial,sans-serif;color:var(--muted)}select{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:4px;padding:11px 14px;font:15px Arial,sans-serif}
.quick-nav{display:flex;justify-content:center;gap:clamp(18px,4vw,42px);flex-wrap:wrap;padding:15px 0;border-bottom:1px solid var(--line)}.quick-nav a{font:700 15px/1.4 Arial,sans-serif;color:var(--accent);text-decoration:none;padding:9px 5px}.quick-nav a:hover{text-decoration:underline;text-underline-offset:5px}.hero{display:grid;grid-template-columns:minmax(250px,350px) minmax(0,1fr);align-items:center;gap:clamp(30px,5vw,68px);padding:48px 0 58px}.cover-frame{padding:14px;background:linear-gradient(145deg,#26313c,#111820);border:1px solid #495461;box-shadow:0 24px 60px #0008}.cover{display:block;width:100%;height:auto;max-height:540px;object-fit:contain}.eyebrow{font:700 12px/1.5 Arial,sans-serif;letter-spacing:.19em;text-transform:uppercase;color:var(--accent)}h1{font:700 clamp(34px,4.5vw,58px)/1.12 Arial,sans-serif;letter-spacing:-.025em;margin:13px 0 10px;overflow-wrap:anywhere}.subtitle{font:600 clamp(18px,2.2vw,24px)/1.5 Arial,sans-serif;color:var(--accent)}.strapline{font-size:19px;line-height:1.7;color:#e9e1d3;margin:20px 0 12px}.overview{font-size:19px;line-height:1.8;max-width:66ch;color:var(--muted);margin:0 0 24px}.price-row{display:flex;align-items:center;gap:20px;flex-wrap:wrap;margin-top:24px}.price{font:700 32px Arial,sans-serif;color:var(--accent)}.buy{display:inline-flex;align-items:center;justify-content:center;min-height:60px;padding:18px 34px;background:var(--accent);color:#17130d;text-decoration:none;font:700 14px Arial,sans-serif;letter-spacing:.08em;text-transform:uppercase;border-radius:3px}.delivery-note{font:14px/1.8 Arial,sans-serif;color:var(--muted);margin:15px 0 0}
.section{padding:42px 0;border-top:1px solid var(--line)}.section-inner{max-width:920px;margin:auto}.section-label{font:700 12px Arial,sans-serif;letter-spacing:.18em;color:var(--accent);text-transform:uppercase}h2{font:700 clamp(25px,3vw,34px)/1.25 Arial,sans-serif;margin:9px 0 20px}.section p{font-size:18.5px;line-height:1.8;color:var(--muted);margin:0 0 16px}.bullet-list{padding:0 0 0 25px;margin:0;color:var(--muted)}.bullet-list li{padding:0 0 11px 5px;font-size:18px;line-height:1.75}.meta-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.meta{padding:18px 20px;background:var(--panel);border:1px solid var(--line);min-width:0}.meta b{display:block;font:700 13px Arial,sans-serif;color:var(--accent);margin-bottom:7px;letter-spacing:.04em}.meta span{font-size:17px;line-height:1.65;color:var(--ink);overflow-wrap:anywhere}.package-list{padding:0 0 0 24px;margin:0}.package-list li{padding:0 0 9px 5px;color:var(--muted);font-size:17px;line-height:1.7;overflow-wrap:anywhere}.book-links{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.book-links a{padding:15px 18px;background:var(--panel);border:1px solid var(--line);color:var(--ink);text-decoration:none;font:600 15px/1.5 Arial,sans-serif}.purchase{padding:50px 0 64px;text-align:center;border-top:1px solid var(--line)}.purchase h2{max-width:760px;margin:10px auto 14px}.purchase p{max-width:760px;margin:0 auto 24px;color:var(--muted);font-size:19px}.purchase .price{margin:0 0 20px}.trust{font:13px/1.8 Arial,sans-serif;color:var(--muted);margin-top:16px}footer{border-top:1px solid var(--line);padding:24px 0 34px;display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;color:var(--muted);font:12px Arial,sans-serif}
[dir="rtl"]{text-align:right}[dir="rtl"] .bullet-list,[dir="rtl"] .package-list{padding-left:0;padding-right:25px}[dir="rtl"] .bullet-list li,[dir="rtl"] .package-list li{padding-left:0;padding-right:5px}[dir="rtl"] .price-row{justify-content:flex-start}
a:focus-visible,select:focus-visible{outline:3px solid var(--accent);outline-offset:4px}
@media(max-width:760px){.shell{width:calc(100% - 30px)}header{padding:12px 0}.hero{grid-template-columns:1fr;gap:28px;padding:26px 0 38px}.cover-frame{width:min(270px,78%);margin:auto;padding:10px}.cover{max-height:390px}.hero-copy{width:100%}h1{font-size:clamp(30px,8vw,42px)}.strapline{font-size:19px}.overview,.section p{font-size:18px;line-height:1.8}.section{padding:34px 0}.meta-grid,.book-links{grid-template-columns:1fr}.buy{width:100%}.price-row{align-items:stretch;flex-direction:column}.purchase{padding:38px 0 48px}footer{flex-direction:column}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
</style></head><body><div class="shell">
<header><a class="brand" href="https://alshayebemad.gumroad.com/">HALL OF <span>GREATNESS</span> PUBLISHING</a><div class="controls"><label for="lang" id="langLabel">Language</label><select id="lang" aria-label="Language"><option value="en">English</option><option value="ar">العربية</option></select></div></header>
<nav class="quick-nav" aria-label="Product page navigation"><a href="#exploreSection" id="navExplore">Explore</a><a href="#editionSection" id="navEdition">Details</a><a href="#purchaseSection" id="navPurchase">Buy</a></nav>
<main>
<section class="hero"><div class="cover-frame"><img class="cover" id="cover" alt="" loading="eager"></div><div class="hero-copy"><div class="eyebrow">HALL OF GREATNESS PUBLISHING · DIGITAL BOOK</div><h1 id="title"></h1><div class="subtitle" id="subtitle"></div><p class="strapline" id="strapline"></p><p class="overview" id="overview"></p><div class="price-row"><div class="price" id="price"></div><a class="buy" id="buy" href="#" data-gumroad-action="buy">Get the book</a></div><p class="delivery-note" id="deliveryNote">Digital edition · Instant delivery through Gumroad · No physical book will be shipped.</p></div></section>
<section class="section" id="exploreSection"><div class="section-inner"><div class="section-label" id="exploreLabel">SUBJECTS AND THEMES</div><h2 id="exploreHeading">What the book examines</h2><ul class="bullet-list" id="explore"></ul></div></section>
<section class="section"><div class="section-inner"><div class="section-label" id="takeawayLabel">READER VALUE</div><h2 id="takeawayHeading">What you will gain</h2><ul class="bullet-list" id="takeaways"></ul></div></section>
<section class="section"><div class="section-inner"><div class="section-label" id="audienceLabel">INTENDED READERS</div><h2 id="audienceHeading">Who should read this book?</h2><p id="audience"></p></div></section>
<section class="section" id="editionSection"><div class="section-inner"><div class="section-label" id="editionLabel">EDITION AND DELIVERY</div><h2 id="editionHeading">Edition information</h2><div class="meta-grid" id="meta"></div></div></section>
<section class="section" id="packageSection"><div class="section-inner"><div class="section-label" id="packageLabel">YOUR DOWNLOAD</div><h2 id="packageHeading">Files included</h2><ol class="package-list" id="package"></ol></div></section>
<section class="section" id="collectionSection"><div class="section-inner"><div class="section-label" id="collectionLabel">THE COMPLETE COLLECTION</div><h2 id="collectionHeading">Explore the five-book series</h2><div class="book-links" id="bookLinks"></div></div></section>
<section class="purchase" id="purchaseSection"><div class="section-label" id="closingLabel">CONTINUE YOUR READING</div><h2 id="closingTitle"></h2><p id="closingText"></p><div class="price" id="priceBottom"></div><a class="buy" id="buyBottom" href="#" data-gumroad-action="buy">Get the book</a><div class="trust" id="trust">Secure checkout through Gumroad · Digital delivery</div></section>
</main><footer><span>HALL OF GREATNESS Publishing · EMAD ALSHAYEB</span><span>Knowledge with Purpose.</span></footer></div>
<script>
const DATA=__DATA__;
const BOOKS=[
["isbsay","THE AI POWER GAME — UNDERSTAND • ADAPT • THRIVE","https://alshayebemad.gumroad.com/l/THEAIPOWERGAME"],
["qsznm","THE AI BLACK BOX","https://alshayebemad.gumroad.com/l/Theaiblackbox"],
["wdwtbf","THE HUMANITY TEST","https://alshayebemad.gumroad.com/l/TheHumanityTest"],
["ylxtub","THE ALGORITHM EMPIRE","https://alshayebemad.gumroad.com/l/THEALGORITHMEMPIRE"],
["qccitx","THE LAST JOB","https://alshayebemad.gumroad.com/l/THELASTJOB"]
];
const el=id=>document.getElementById(id);
function list(id,items){const box=el(id);box.replaceChildren();(items||[]).forEach(x=>{const li=document.createElement("li");li.textContent=x;box.append(li)})}
function render(code){
 code=resolveLanguage(code);const t=DATA.translations[code]||DATA.translations.en,u=t.ui||DATA.translations.en.ui||{},w=k=>u[k]||DATA.translations.en.ui[k]||k,rtl=!!((DATA.languages||[]).find(x=>x.code===code)||{}).rtl;
 document.title=t.title+" | HALL OF GREATNESS Publishing";
 const description=document.querySelector('meta[name="description"]'); if(description) description.content=t.overview;
 document.documentElement.lang=code;document.documentElement.dir=rtl?"rtl":"ltr";el("lang").value=code;
 el("langLabel").textContent=w("landingLanguage");el("navExplore").textContent=w("landingStory");el("navEdition").textContent=w("landingDetails");el("navPurchase").textContent=w("landingPurchase");el("buy").textContent=w("landingBuy");el("buyBottom").textContent=w("landingBuy");
 el("deliveryNote").textContent=w("landingDelivery");el("exploreLabel").textContent=w("landingStory");el("exploreHeading").textContent=w("landingStoryHeading");
 el("takeawayLabel").textContent=w("landingReaderValue");el("takeawayHeading").textContent=w("landingReaderValueHeading");el("audienceLabel").textContent=w("landingAudience");el("audienceHeading").textContent=w("landingAudienceHeading");
 el("editionLabel").textContent=w("landingEdition");el("editionHeading").textContent=w("landingEditionHeading");el("packageLabel").textContent=w("landingPackage");el("packageHeading").textContent=w("landingPackageHeading");
 el("collectionLabel").textContent=w("landingCollection");el("collectionHeading").textContent=w("landingCollectionHeading");el("closingLabel").textContent=w("landingContinue");el("trust").textContent=w("landingTrust");
 el("title").textContent=t.title;el("subtitle").textContent=t.subtitle;el("strapline").textContent=t.strapline;el("overview").textContent=t.overview;
 el("audience").textContent=t.audience;el("closingTitle").textContent=t.strapline;el("closingText").textContent=t.cta;
 list("explore",t.explore);list("takeaways",t.takeaways);list("package",t.package);
 const meta=[["Author","EMAD ALSHAYEB"],["Publisher","HALL OF GREATNESS Publishing"],["Language",code==="ar"?"الإنجليزية":"English"],["Structure",t.structure],["Format",t.format],["Delivery",t.delivery]];
 const m=el("meta");m.replaceChildren();meta.forEach((x,i)=>{const d=document.createElement("div");d.className="meta";const b=document.createElement("b");b.textContent=w(["landingMetaAuthor","landingMetaPublisher","landingMetaLanguage","landingMetaStructure","landingMetaFormat","landingMetaDelivery"][i]);const s=document.createElement("span");s.textContent=x[1];d.append(b,s);m.append(d)});
 el("packageSection").hidden=!t.package.length;el("collectionSection").hidden=DATA.product.name.indexOf("COLLECTION")<0;
 const links=el("bookLinks");links.replaceChildren();BOOKS.forEach(([id,name,url])=>{if(id===DATA.key)return;const a=document.createElement("a");a.href=url;a.textContent=name;links.append(a)});
 el("cover").src=DATA.product.cover;el("cover").alt=t.title+" book cover";
el("buy").href=DATA.product.url;el("buyBottom").href=DATA.product.url;
 const price="$"+Number(DATA.product.price).toFixed(2)+" USD";el("price").textContent=price;el("priceBottom").textContent=price;
}
function resolveLanguage(code){
 if(code!=="auto")return DATA.translations[code]?code:"en";
 const prefs=navigator.languages&&navigator.languages.length?navigator.languages:[navigator.language||"en"];
 for(const pref of prefs){const exact=(DATA.languages||[]).find(x=>x.code.toLowerCase()===pref.toLowerCase());if(exact)return exact.code;const base=pref.split("-")[0];const match=(DATA.languages||[]).find(x=>x.code===base);if(match)return match.code;}
 return "en";
}
const languageSelect=el("lang");languageSelect.replaceChildren();
const autoOption=document.createElement("option");autoOption.value="auto";autoOption.textContent="🌐 Auto";languageSelect.append(autoOption);
(DATA.languages||[{code:"en",name:"English"}]).forEach(x=>{const option=document.createElement("option");option.value=x.code;option.textContent=x.name;languageSelect.append(option)});
const saved=(()=>{try{return localStorage.getItem("hog-language")||"auto"}catch(e){return "auto"}})();
render(saved);
languageSelect.addEventListener("change",e=>{const value=e.target.value;try{if(value==="auto")localStorage.removeItem("hog-language");else localStorage.setItem("hog-language",value)}catch(err){}render(value)});
</script></body></html>"""
def main():
 generated=[]
 for key in sorted(EXPECTED):
  p=PRODUCTS[key]
  page=render(key)
  dest=ROOT/"gumroad-ebook-landings"/key/"landing.html"
  dest.parent.mkdir(parents=True,exist_ok=True); dest.write_text(page,encoding="utf-8")
  generated.append({"permalink":key,"name":p["name"],"file":str(dest.relative_to(ROOT))})
 (OUT/"generated-pages.json").write_text(json.dumps(generated,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 if LOCAL_ONLY:
  report={"generated":len(generated),"previewed":0,"published":0,"errors":0,"mode":"local-only"}
  (OUT/"refresh-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  print(json.dumps(report,ensure_ascii=False))
  return
 results=[]
 for item in generated:
  key=item["permalink"]; path=item["file"]; last=""
  for attempt in range(4):
   r=subprocess.run(["gumroad","products","page","preview",GUMROAD_IDS[key],path,"--json","--no-input","--non-interactive"],cwd=ROOT,env=ENV,text=True,capture_output=True)
   raw=r.stdout or r.stderr; last=raw[-1600:]
   try: payload=json.loads(raw)
   except Exception: payload={}
   if r.returncode==0 and payload.get("success") is True:
    report=payload.get("sanitization_report") or {}
    # Gumroad's preview sanitizer removes these non-rendering document-head
    # elements by design. Permit only this exact set; any content, style, or
    # attribute removal remains a hard safety stop.
    expected_head_removals = {
     ("meta", (("charset", "utf-8"),)),
     ("title", ()),
     ("meta", (("content", "Bilingual editorial e-book product page from HALL OF GREATNESS Publishing."), ("name", "description"))),
     ("link", (("href", "data:,"), ("rel", "icon"))),
    }
    removed_tags = report.get("removed_tags") or []
    actual_head_removals = {
     (entry.get("tag"), tuple(sorted((entry.get("attrs") or {}).items())))
     for entry in removed_tags
    }
    safe_head_only = (
     len(removed_tags) == len(expected_head_removals)
     and actual_head_removals == expected_head_removals
     and report.get("removed_attributes") == []
     and report.get("total_removed") == len(expected_head_removals)
     and report.get("truncated") is False
    )
    if not safe_head_only:
     results.append({"permalink":key,"status":"blocked_sanitization","report":report}); break
    (OUT/(key+"-preview.json")).write_text(raw,encoding="utf-8")
    results.append({"permalink":key,"status":"preview_ok"}); break
   err=payload.get("error") or {}
   transient=err.get("code")=="api_error" and ("temporary" in err.get("message","").lower() or "try again" in err.get("message","").lower())
   if not transient:
    results.append({"permalink":key,"status":"preview_error","error":last}); break
   if attempt<3: time.sleep(10*(attempt+1))
  else: results.append({"permalink":key,"status":"preview_temporary_outage","error":last})
  if results[-1]["status"]!="preview_ok": break
 if len(results)!=len(generated) or any(x["status"]!="preview_ok" for x in results):
  (OUT/"refresh-report.json").write_text(json.dumps({"generated":len(generated),"published":0,"results":results},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  raise SystemExit("Safe stop: ebook preview failed; no ebook pages were published.")
 # Preview-only safeguard: publishing requires a separate, explicit approval and workflow.

 report={"generated":len(generated),"previewed":sum(x["status"]=="preview_ok" for x in results),"published":0,"errors":sum(x["status"] not in ("preview_ok","published") for x in results),"results":results}
 (OUT/"refresh-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({k:report[k] for k in ("generated","previewed","published","errors")},ensure_ascii=False))
 if report["errors"]: raise SystemExit(1)
if __name__=="__main__": main()
