#!/usr/bin/env python3
"""Build, preview and safely publish the refreshed multilingual Gumroad landing pages."""
import hashlib, html, json, os, re, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAT=json.loads((ROOT/"catalog-data.json").read_text(encoding="utf-8"))
EBOOK_COPY=json.loads((ROOT/"ebook-copy.json").read_text(encoding="utf-8"))
REG=json.loads((ROOT/"locales/languages.json").read_text(encoding="utf-8"))["languages"]
I18N=(ROOT/"assets/i18n.js").read_text(encoding="utf-8")
m=re.search(r"const M=(\{[\s\S]*?\});\nconst map=",I18N)
if not m: raise SystemExit("Cannot read UI translations.")
UI=json.loads(m.group(1))
LOCAL_ONLY="--local-only" in __import__("sys").argv[1:]
PREVIEW_PERMALINK=os.environ.get("PREVIEW_PERMALINK","mxrljy").strip()
TOKEN=os.environ.get("GUMROAD_ACCESS_TOKEN","").strip()
if not LOCAL_ONLY and not TOKEN: raise SystemExit("GUMROAD_ACCESS_TOKEN is required.")
ENV=os.environ.copy()
EVIDENCE=ROOT/"gumroad-landing-refresh-evidence"; EVIDENCE.mkdir(exist_ok=True)
def digest(obj): return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
ALLOWED_DETAIL_KEYS={"files_included","product_type","delivery","physical_item","printing","usage","bundle_item_count","structure"}
PAGE_CHROME=re.compile(r"add to wishlist|powered by gumroad|more from this creator|explore our collection|available on gumroad",re.I)
SHARE_LABELS={"share","Partager","Compartir","Anteil","Compartilhar","Condividi","Поделиться","शेयर","শেয়ার","シェア","份额"}
def clean_page_copy(value):
    if not isinstance(value,str): return ""
    lines=value.strip().splitlines()
    while lines and lines[0].strip().strip(":") in SHARE_LABELS:
        lines.pop(0)
    return "\\n".join(lines).strip()
def translation_text_is_safe(value, max_length=12000, min_length=8):
    if not isinstance(value,str): return False
    text=clean_page_copy(value)
    if not text or len(text)>max_length or len(text)<min_length: return False
    if not re.search(r"[\\w\\u0600-\\u06FF]",text,re.UNICODE): return False
    if re.search(r"(.)\\1{5,}",text,re.I): return False
    if PAGE_CHROME.search(text): return False
    if re.search(r"[\\uFFFD]|(?:Ã.|Â.|Ø[ء-ي]|Ù[ء-ي])",text): return False
    if text.strip(" .。،,:;!?-—…")=="": return False
    return True
def ebook_page_copy(source):
    overview=source.get("overview","")
    summary=overview if translation_text_is_safe(overview, min_length=30) else source.get("strapline","")
    paragraphs=[source.get("strapline",""),overview]
    for field in ("explore","takeaways"):
        values=source.get(field) or []
        if values: paragraphs.append("\\n".join("• "+str(x) for x in values))
    if source.get("audience"): paragraphs.append(source["audience"])
    if source.get("cta"): paragraphs.append(source["cta"])
    full="\\n\\n".join(x for x in paragraphs if x)
    details={
      "product_type":source.get("format","Digital book"),
      "delivery":source.get("delivery","Digital delivery through Gumroad"),
      "structure":source.get("structure",""),
    }
    if source.get("package"): details["files_included"]="; ".join(source["package"])
    return {"name":source.get("title",""),"summary":summary,"full_description":full,"details":details}
def esc(v): return html.escape(str(v or ""),quote=True)
def js(v): return json.dumps(v,ensure_ascii=False).replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
def slug(v): return re.sub(r"[^a-z0-9]+","-",str(v).lower()).strip("-") or "product"
PROTECTED_UNPUBLISHED={"jrsgce","ukxrmq","yhkokf","nxkxyq"}
products=[p for p in CAT.get("products",[]) if p.get("published") and p.get("permalink") not in PROTECTED_UNPUBLISHED and p.get("url","").startswith("https://") and p.get("cover_url","").startswith("https://")]
if LOCAL_ONLY:
    products=[p for p in products if p.get("permalink")==PREVIEW_PERMALINK]
    if len(products)!=1:
        raise SystemExit(f"Local preview requires exactly one published product; found {len(products)} for {PREVIEW_PERMALINK!r}.")
groups={}
for p in products: groups.setdefault(p.get("content_type",""),[]).append(p)
def translations(p):
    key=p["permalink"]
    fields={k:p.get(k) for k in ("summary","full_description","category") if p.get(k)}
    fields["product_details"]=p.get("product_details") or {}
    expected=digest(fields)
    out={}
    english_ui=UI.get("en",{})
    if p.get("content_type")=="ebook" and key in EBOOK_COPY:
        base=ebook_page_copy(EBOOK_COPY[key].get("en",{}))
        out["en"]={**base,"ui":english_ui}
    else:
        base_summary=p.get("summary","")
        base_full=clean_page_copy(p.get("full_description") or base_summary)
        if not translation_text_is_safe(base_summary, min_length=20):
            base_summary=p.get("name","")
        if not translation_text_is_safe(base_full, min_length=20):
            base_full=base_summary
        base_details=p.get("product_details") or {}
        base_details={k:v for k,v in base_details.items() if k in ALLOWED_DETAIL_KEYS and translation_text_is_safe(v,max_length=500,min_length=3)}
        out["en"]={"name":p["name"],"summary":base_summary,"full_description":base_full,"details":base_details,"ui":english_ui}
    for lang in REG:
        code=lang["code"]
        if code=="en" or not lang.get("available"): continue
        locale_path=ROOT/"locales"/(code+".json")
        if not locale_path.exists(): continue
        try: loc=json.loads(locale_path.read_text(encoding="utf-8"))
        except Exception: continue
        localized_ui=loc.get("ui") or UI.get(code) or english_ui
        if p.get("content_type")=="ebook" and key in EBOOK_COPY:
            item=(loc.get("ebooks") or {}).get(key,{})
            source_hash=digest(EBOOK_COPY[key].get("en",{}))
            if item.get("_source_hash")!=source_hash: continue
            translated=ebook_page_copy(item)
            if not translation_text_is_safe(translated["summary"],min_length=30): continue
            if not translation_text_is_safe(translated["full_description"],min_length=40): continue
            out[code]={**translated,"ui":localized_ui}
            continue
        item=(loc.get("products") or {}).get(key,{})
        if item.get("_source_hash")!=expected: continue
        summary=item.get("summary","")
        if not translation_text_is_safe(summary,min_length=20): continue
        full=clean_page_copy(item.get("full_description",""))
        if not translation_text_is_safe(full,min_length=40):
            full=summary
        details=item.get("product_details") or {}
        details={k:v for k,v in details.items() if k in ALLOWED_DETAIL_KEYS and translation_text_is_safe(v,max_length=500,min_length=3)}
        localized_name=item.get("title_ar") if code=="ar" else p["name"]
        out[code]={"name":localized_name or p["name"],"summary":summary,"full_description":full,"details":details,"ui":localized_ui}
    return out
def render(p):
    tr=translations(p); related=[{"name":x["name"],"url":x["url"]} for x in groups.get(p.get("content_type",""),[]) if x["permalink"]!=p["permalink"]][:4]
    languages=[{"code":"en","name":"English","rtl":False}]+[{"code":x["code"],"name":x["name"],"rtl":bool(x.get("rtl"))} for x in REG if x["code"] in tr and x["code"]!="en"]
    kind={"art-decor":"DIGITAL ARTWORK","ebook":"DIGITAL BOOK","course":"DIGITAL COURSE"}.get(p.get("content_type"),"DIGITAL PRODUCT")
    data={"translations":tr,"related":related}
    name=esc(p["name"]); cover=esc(p["cover_url"]); summary=esc(p.get("summary",""))
    page=f"""<!doctype html><html lang="en" dir="ltr"><head>
<style>
:root{{--bg:#141310;--surface:#201d18;--ink:#f5eee2;--muted:#d0c5b4;--gold:#dfbd78;--line:#514634}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--bg);color:var(--ink);font:18px/1.8 Georgia,"Times New Roman",serif}}a{{color:var(--gold)}}.shell{{width:min(980px,calc(100% - 40px));margin:auto}}
header{{min-height:76px;display:flex;align-items:center;justify-content:space-between;gap:16px;border-bottom:1px solid var(--line);flex-wrap:wrap}}.brand{{font:700 13px Arial,sans-serif;letter-spacing:.19em;color:var(--ink);text-decoration:none}}.brand span{{color:var(--gold)}}.controls{{display:flex;align-items:center;gap:9px}}.controls label{{font:13px Arial,sans-serif;color:var(--muted)}}select{{max-width:190px;background:var(--surface);color:var(--ink);border:1px solid var(--line);padding:10px;font:14px Arial,sans-serif}}
.quick-nav{{display:flex;justify-content:center;gap:clamp(18px,4vw,42px);flex-wrap:wrap;padding:16px 0;border-bottom:1px solid var(--line)}}.quick-nav a{{font:700 15px/1.4 Arial,sans-serif;color:var(--gold);text-decoration:none;padding:8px 4px}}.quick-nav a:hover{{text-decoration:underline;text-underline-offset:5px}}
.hero{{display:flex;flex-direction:column;align-items:stretch;padding:30px 0 46px}}.art-wrap{{width:100%;max-width:940px;margin:0 auto 36px;padding:clamp(10px,2vw,18px);background:var(--surface);border:1px solid var(--line);box-shadow:0 20px 55px #0005}}.art{{display:block;width:100%;height:auto;max-height:none;object-fit:contain}}.hero-copy{{width:100%;max-width:880px;margin:auto}}
.kicker{{font:12px/1.5 Arial,sans-serif;letter-spacing:.2em;text-transform:uppercase;color:var(--gold)}}.hero-copy,.section-inner{{text-align:start}}h1{{font-size:clamp(34px,4.5vw,56px);line-height:1.12;font-weight:400;margin:12px 0 18px;overflow-wrap:anywhere}}.subtitle{{font-size:clamp(20px,2.4vw,25px);font-style:italic;color:var(--gold)}}.summary,.description,.copy{{font-size:18px;line-height:1.8;color:var(--muted);white-space:pre-line;text-align:start;max-width:68ch;text-wrap:pretty}}.summary{{margin:18px 0 24px}}.full-copy{{max-width:68ch;color:var(--muted);font-size:16px;line-height:1.75}}.full-copy summary{{display:inline-block;cursor:pointer;color:var(--gold);font:700 14px/1.5 Arial,sans-serif;padding:10px 0;text-underline-offset:4px}}.full-copy .description{{padding-top:12px;font-size:17px;line-height:1.75}}
.price-line{{display:flex;align-items:center;gap:20px;flex-wrap:wrap;margin:26px 0 12px}}.price{{font:34px Arial,sans-serif;color:var(--gold)}}.buy{{display:inline-flex;align-items:center;justify-content:center;min-height:64px;padding:18px 34px;background:var(--gold);color:#17130d;border:1px solid var(--gold);text-decoration:none;font:700 14px Arial,sans-serif;letter-spacing:.1em;text-transform:uppercase}}.fine{{font:14px/1.8 Arial,sans-serif;color:var(--muted);margin-top:14px}}
.section{{padding:44px 0;border-top:1px solid var(--line)}}.section-inner{{max-width:880px;margin:auto}}h2{{font-size:clamp(25px,3.4vw,34px);line-height:1.2;font-weight:400;margin:8px 0 20px}}.details,.related{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:22px}}.detail,.related a{{padding:17px 19px;border:1px solid var(--line);background:var(--surface)}}.detail b{{display:block;color:var(--gold);font:600 14px Arial,sans-serif;margin-bottom:6px}}.detail span{{font-size:17px;line-height:1.65;color:var(--muted)}}.related a{{display:block;text-decoration:none;font-size:17px;line-height:1.6}}
.purchase{{padding:48px 0 60px;text-align:center;border-top:1px solid var(--line)}}.purchase p{{max-width:760px;margin:0 auto 22px;color:var(--muted);font-size:18px}}.trust{{font:13px/1.8 Arial,sans-serif;color:var(--muted);margin-top:16px}}footer{{border-top:1px solid var(--line);padding:24px 0 34px;display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;color:var(--muted);font:12px Arial,sans-serif}}
[dir="rtl"]{{text-align:right}}a:focus-visible,select:focus-visible{{outline:3px solid var(--gold);outline-offset:4px}}
@media(max-width:680px){{.shell{{width:calc(100% - 28px)}}header{{padding:12px 0;min-height:68px}}.hero{{padding:20px 0 34px}}.art-wrap{{margin-bottom:25px;padding:9px}}.summary,.description,.copy{{font-size:17px;line-height:1.75}}.full-copy .description{{font-size:16px;line-height:1.7}}.details,.related{{grid-template-columns:1fr}}.price-line{{align-items:stretch;flex-direction:column}}.buy{{width:100%}}footer{{flex-direction:column}}}}
@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{scroll-behavior:auto!important;transition:none!important;animation:none!important}}}}
</style></head><body><div class="shell">
<header><a class="brand" href="https://alshayebemad.gumroad.com/">HALL OF <span>GREATNESS</span></a><div class="controls"><label for="lang" id="languageLabel">Choose language</label><select id="lang" aria-label="Choose language"></select></div></header>
<nav class="quick-nav" aria-label="Product page navigation"><a href="#story" id="navStory">Story</a><a href="#details" id="navDetails">Details</a><a href="#purchase" id="navBuy">Buy</a></nav>
<main><section class="hero"><div class="art-wrap"><img class="art" src="{cover}" alt="{name} cover" loading="eager"></div><div class="hero-copy"><div class="kicker">{kind} · HALL OF GREATNESS</div><h1 id="productTitle">{name}</h1><div class="subtitle" id="subtitle"></div><p class="summary" id="summary">{summary}</p><div class="price-line"><div class="price" data-gumroad-field="price"></div><a class="buy" href="#" data-gumroad-action="buy" id="buy">Get this digital product</a></div><p class="fine" id="delivery">Instant digital delivery after purchase. Please review the product details before purchase.</p></div></section>
<section class="section" id="story"><div class="section-inner"><div class="kicker" id="storyLabel">THE STORY</div><h2 id="storyTitle">The meaning behind this product</h2><details class="full-copy"><summary id="fullDescriptionToggle">Read the full product story</summary><div class="description" id="fullDescription"></div></details></div></section>
<section class="section" id="details"><div class="section-inner"><div class="kicker" id="detailsLabel">PRODUCT DETAILS</div><h2 id="detailsTitle">What you should know</h2><div class="details" id="details"></div></div></section>
<section class="section"><div class="section-inner"><div class="kicker" id="relatedLabel">EXPLORE MORE</div><h2 id="relatedTitle">More from HALL OF GREATNESS</h2><div class="related" id="related"></div></div></section>
<section class="purchase" id="purchase"><div class="kicker" id="purchaseLabel">MAKE IT YOURS</div><h2 id="purchaseTitle">Bring this story into your world.</h2><p id="purchaseText">{summary}</p><div class="price" data-gumroad-field="price"></div><a class="buy" href="#" data-gumroad-action="buy" id="buyBottom">Get this digital product</a><div class="trust">Secure checkout through Gumroad · Instant digital delivery</div><div class="trust" data-gumroad-field="rating"></div><div class="trust" data-gumroad-field="review-count"></div></section></main>
<footer><span>HALL OF GREATNESS</span><span>Art with a Soul. A Message Without Borders.</span></footer></div>
<script>const DATA=__DATA__;const LANGS=__LANGS__;const select=document.getElementById("lang");const autoOption=document.createElement("option");autoOption.value="auto";autoOption.textContent="🌐 Auto";select.appendChild(autoOption);LANGS.forEach(x=>{{const o=document.createElement("option");o.value=x.code;o.textContent=x.name;select.appendChild(o)}});const ENUI=(DATA.translations.en||{{}}).ui||{{}};function preferredLanguage(){{const prefs=navigator.languages&&navigator.languages.length?navigator.languages:[navigator.language||"en"];for(const pref of prefs){{const exact=LANGS.find(x=>x.code.toLowerCase()===pref.toLowerCase());if(exact)return exact.code;const base=pref.split("-")[0];const match=LANGS.find(x=>x.code===base);if(match)return match.code;}}return "en";}}function setLanguage(code){{const actual=code==="auto"?preferredLanguage():code;const t=DATA.translations[actual]||DATA.translations.en;const u=t.ui||ENUI;const w=k=>u[k]||ENUI[k]||k;const rtl=!!((LANGS.find(x=>x.code===actual)||{{}}).rtl);document.documentElement.lang=actual;document.documentElement.dir=rtl?"rtl":"ltr";document.getElementById("languageLabel").textContent=w("landingLanguage");document.getElementById("buy").textContent=w("landingBuy");document.getElementById("buyBottom").textContent=w("landingBuy");document.getElementById("delivery").textContent=w("landingDelivery");document.getElementById("storyLabel").textContent=w("landingStory");document.getElementById("storyTitle").textContent=w("landingStoryHeading");document.getElementById("detailsLabel").textContent=w("landingDetails");document.getElementById("detailsTitle").textContent=w("landingDetailsHeading");document.getElementById("relatedLabel").textContent=w("landingRelated");document.getElementById("relatedTitle").textContent=w("landingRelatedHeading");document.getElementById("purchaseLabel").textContent=w("landingPurchase");document.getElementById("purchaseTitle").textContent=w("landingPurchaseHeading");document.getElementById("navStory").textContent=w("landingStory");document.getElementById("navDetails").textContent=w("landingDetails");document.getElementById("navBuy").textContent=w("landingPurchase");document.getElementById("productTitle").textContent=t.name;document.getElementById("summary").textContent=t.summary;document.getElementById("purchaseText").textContent=t.summary;document.getElementById("fullDescription").textContent=t.full_description;document.getElementById("fullDescriptionToggle").textContent=w("landingReadMore");document.querySelector(".purchase .trust").textContent=w("landingSecureCheckout");const detailKeys={{product_type:"landingDetailProductType",delivery:"landingDetailDelivery",physical_item:"landingDetailPhysical",printing:"landingDetailPrinting",usage:"landingDetailUsage",files_included:"landingDetailFiles",bundle_item_count:"landingDetailCollection",structure:"landingDetailStructure"}};const box=document.getElementById("details");box.replaceChildren();Object.entries(t.details||{{}}).forEach(([k,v])=>{{if(!v)return;const i=document.createElement("div");i.className="detail";const b=document.createElement("b");b.textContent=w(detailKeys[k]||k);const s=document.createElement("span");s.textContent=v;i.append(b,s);box.append(i)}});const rel=document.getElementById("related");rel.replaceChildren();DATA.related.forEach(x=>{{const a=document.createElement("a");a.href=x.url;a.target="_blank";a.rel="noopener noreferrer";a.textContent=x.name;rel.append(a)}});if(select.value!==actual)select.value=actual;}}const saved=(()=>{{try{{return localStorage.getItem("hog-language")||"auto"}}catch(e){{return "auto"}}}})();select.addEventListener("change",()=>{{const v=select.value;try{{if(v==="auto")localStorage.removeItem("hog-language");else localStorage.setItem("hog-language",v)}}catch(e){{}}setLanguage(v)}});setLanguage(saved);</script></body></html>"""
    return page.replace("__DATA__",js(data)).replace("__LANGS__",js(languages))
generated=[]
for p in products:
    path=ROOT/"gumroad-landings"/slug(p.get("landing_slug") or p["name"])/"landing.html"
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(render(p),encoding="utf-8")
    generated.append({"permalink":p["permalink"],"name":p["name"],"file":str(path.relative_to(ROOT))})
(EVIDENCE/"generated-pages.json").write_text(json.dumps(generated,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("Generated",len(generated),"published product pages.")
if LOCAL_ONLY:
    report={"generated":len(generated),"previewed":0,"published":0,"errors":0,"mode":"local-only","products":generated}
    (EVIDENCE/"refresh-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    raise SystemExit(0)
outcomes=[]
for x in generated:
    key=x["permalink"]; path=x["file"]
    r=None
    # Gumroad occasionally returns a transient review-service error (HTTP 200).
    # Retry only that temporary service failure; never bypass a failed preview.
    for attempt in range(4):
        r=subprocess.run(["gumroad","products","page","preview",key,path,"--json","--no-input","--non-interactive"],cwd=ROOT,env=ENV,text=True,capture_output=True)
        if r.returncode == 0:
            try:
                payload=json.loads(r.stdout)
            except Exception:
                payload={}
            if payload.get("success") is True:
                break
            error=payload.get("error") or {}
            temporary=(error.get("code")=="api_error" and ("temporary issue" in error.get("message","").lower() or "try again" in error.get("message","").lower()))
            if not temporary:
                outcomes.append({"permalink":key,"status":"preview_error","error":payload}); break
        else:
            raw=(r.stderr or r.stdout)
            try:
                payload=json.loads(raw)
                error=payload.get("error") or {}
            except Exception:
                error={}
            temporary=(error.get("code")=="api_error" and ("temporary issue" in error.get("message","").lower() or "try again" in error.get("message","").lower()))
            if not temporary:
                outcomes.append({"permalink":key,"status":"preview_error","error":raw[-1200:]}); break
        if attempt < 3:
            delay=10*(attempt+1)
            print(f"Temporary Gumroad preview outage for {key}; retry {attempt+1}/3 in {delay}s.")
            time.sleep(delay)
    else:
        outcomes.append({"permalink":key,"status":"preview_temporary_outage","error":(r.stderr or r.stdout)[-1200:]})
    if outcomes and outcomes[-1].get("permalink")==key and outcomes[-1]["status"]!="preview_ok":
        break
    if r is None or r.returncode:
        if not outcomes or outcomes[-1].get("permalink")!=key:
            outcomes.append({"permalink":key,"status":"preview_error","error":(r.stderr or r.stdout)[-1200:]})
        break
    try: payload=json.loads(r.stdout)
    except Exception: payload={}
    if payload.get("success") is not True:
        outcomes.append({"permalink":key,"status":"preview_error","error":payload}); break
    report=payload.get("sanitization_report")
    (EVIDENCE/(key+"-preview.json")).write_text(r.stdout,encoding="utf-8")
    if not isinstance(report,dict) or report.get("removed_tags")!=[] or report.get("removed_attributes")!=[] or report.get("total_removed")!=0 or report.get("truncated") is not False:
        outcomes.append({"permalink":key,"status":"blocked_sanitization","report":report}); break
    outcomes.append({"permalink":key,"status":"preview_ok"})
if len(outcomes)!=len(generated) or any(x["status"]!="preview_ok" for x in outcomes):
    (EVIDENCE/"refresh-report.json").write_text(json.dumps({"generated":len(generated),"published":0,"results":outcomes},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    raise SystemExit("Safe stop: at least one page failed preview; no Gumroad pages were published.")
for x in generated:
    key=x["permalink"]; path=x["file"]
    r=subprocess.run(["gumroad","products","page","publish",key,path,"--json","--no-input","--non-interactive"],cwd=ROOT,env=ENV,text=True,capture_output=True)
    if r.returncode:
        outcomes.append({"permalink":key,"status":"publish_error","error":(r.stderr or r.stdout)[-1200:]}); break
    u=subprocess.run(["gumroad","products","page","url",key,"--json","--jq",".product.landing_url","--no-input","--non-interactive"],cwd=ROOT,env=ENV,text=True,capture_output=True)
    url=(u.stdout or "").strip().strip('"')
    outcomes.append({"permalink":key,"status":"published" if u.returncode==0 and url.startswith("https://") else "url_unverified","landing_url":url})
    if outcomes[-1]["status"]!="published": break
report={"generated":len(generated),"previewed":sum(x["status"]=="preview_ok" for x in outcomes),"published":sum(x["status"]=="published" for x in outcomes),"errors":sum(x["status"] not in ("preview_ok","published") for x in outcomes),"results":outcomes}
(EVIDENCE/"refresh-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:report[k] for k in ("generated","previewed","published","errors")},ensure_ascii=False))
if report["errors"]: raise SystemExit(1)
