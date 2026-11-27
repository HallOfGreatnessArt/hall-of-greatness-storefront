#!/usr/bin/env python3
"""Build, preview and safely publish the refreshed multilingual Gumroad landing pages."""
import hashlib, html, json, os, re, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAT=json.loads((ROOT/"catalog-data.json").read_text(encoding="utf-8"))
REG=json.loads((ROOT/"locales/languages.json").read_text(encoding="utf-8"))["languages"]
I18N=(ROOT/"assets/i18n.js").read_text(encoding="utf-8")
m=re.search(r"const M=(\{[\s\S]*?\});\nconst map=",I18N)
if not m: raise SystemExit("Cannot read UI translations.")
UI=json.loads(m.group(1))
TOKEN=os.environ.get("GUMROAD_ACCESS_TOKEN","").strip()
if not TOKEN: raise SystemExit("GUMROAD_ACCESS_TOKEN is required.")
ENV=os.environ.copy()
EVIDENCE=ROOT/"gumroad-landing-refresh-evidence"; EVIDENCE.mkdir(exist_ok=True)
def digest(obj): return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def esc(v): return html.escape(str(v or ""),quote=True)
def js(v): return json.dumps(v,ensure_ascii=False).replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
def slug(v): return re.sub(r"[^a-z0-9]+","-",str(v).lower()).strip("-") or "product"
products=[p for p in CAT.get("products",[]) if p.get("published") and p.get("permalink") and p.get("url","").startswith("https://") and p.get("cover_url","").startswith("https://")]
groups={}
for p in products: groups.setdefault(p.get("content_type",""),[]).append(p)
def translations(p):
    key=p["permalink"]; fields={k:p.get(k) for k in ("summary","full_description","category") if p.get(k)}; fields["product_details"]=p.get("product_details") or {}
    expected=digest(fields)
    out={"en":{"name":p["name"],"summary":p.get("summary",""),"full_description":p.get("full_description") or p.get("summary",""),"details":p.get("product_details") or {}}}
    for lang in REG:
        code=lang["code"]
        if code=="en" or not lang.get("available"): continue
        path=ROOT/"locales"/(code+".json")
        if not path.exists(): continue
        try: loc=json.loads(path.read_text(encoding="utf-8"))
        except Exception: continue
        item=loc.get("products",{}).get(key,{})
        if item.get("_source_hash")!=expected or not item.get("summary") or not item.get("full_description"): continue
        out[code]={"name":item.get("title_ar") or p["name"],"summary":item["summary"],"full_description":item["full_description"],"details":item.get("product_details") or p.get("product_details") or {}}
    return out
def render(p):
    tr=translations(p); related=[{"name":x["name"],"url":x["url"]} for x in groups.get(p.get("content_type",""),[]) if x["permalink"]!=p["permalink"]][:4]
    languages=[{"code":"en","name":"English"}]+[{"code":x["code"],"name":x["name"]} for x in REG if x["code"] in tr and x["code"]!="en"]
    kind={"art-decor":"DIGITAL ARTWORK","ebook":"DIGITAL BOOK","course":"DIGITAL COURSE"}.get(p.get("content_type"),"DIGITAL PRODUCT")
    data={"translations":tr,"related":related}
    name=esc(p["name"]); cover=esc(p["cover_url"]); summary=esc(p.get("summary",""))
    page=f"""<!doctype html><html lang="en" dir="ltr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{summary}"><title>{name} | HALL OF GREATNESS</title>
<style>
:root{{--bg:#141310;--surface:#201d18;--ink:#f5eee2;--muted:#d0c5b4;--gold:#dfbd78;--line:#514634}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--bg);color:var(--ink);font:19px/1.85 Georgia,"Times New Roman",serif}}a{{color:var(--gold)}}.shell{{width:min(980px,calc(100% - 40px));margin:auto}}
header{{min-height:76px;display:flex;align-items:center;justify-content:space-between;gap:16px;border-bottom:1px solid var(--line);flex-wrap:wrap}}.brand{{font:700 13px Arial,sans-serif;letter-spacing:.19em;color:var(--ink);text-decoration:none}}.brand span{{color:var(--gold)}}.controls{{display:flex;align-items:center;gap:9px}}.controls label{{font:13px Arial,sans-serif;color:var(--muted)}}select{{max-width:190px;background:var(--surface);color:var(--ink);border:1px solid var(--line);padding:10px;font:14px Arial,sans-serif}}
.hero{{display:flex;flex-direction:column;align-items:stretch;padding:30px 0 46px}}.art-wrap{{width:100%;max-width:940px;margin:0 auto 36px;padding:clamp(10px,2vw,18px);background:var(--surface);border:1px solid var(--line);box-shadow:0 20px 55px #0005}}.art{{display:block;width:100%;height:auto;max-height:none;object-fit:contain}}.hero-copy{{width:100%;max-width:880px;margin:auto}}
.kicker{{font:12px/1.5 Arial,sans-serif;letter-spacing:.2em;text-transform:uppercase;color:var(--gold)}}h1{{font-size:clamp(34px,5vw,58px);line-height:1.12;font-weight:400;margin:12px 0 16px;overflow-wrap:anywhere}}.subtitle{{font-size:clamp(20px,2.4vw,25px);font-style:italic;color:var(--gold)}}.summary,.description,.copy{{font-size:clamp(18px,2vw,21px);line-height:1.9;color:var(--muted);white-space:pre-line}}.summary{{margin:20px 0 26px}}
.price-line{{display:flex;align-items:center;gap:20px;flex-wrap:wrap;margin:26px 0 12px}}.price{{font:34px Arial,sans-serif;color:var(--gold)}}.buy{{display:inline-flex;align-items:center;justify-content:center;min-height:58px;padding:16px 30px;background:var(--gold);color:#17130d;border:1px solid var(--gold);text-decoration:none;font:700 14px Arial,sans-serif;letter-spacing:.1em;text-transform:uppercase}}.fine{{font:14px/1.8 Arial,sans-serif;color:var(--muted);margin-top:14px}}
.section{{padding:44px 0;border-top:1px solid var(--line)}}.section-inner{{max-width:880px;margin:auto}}h2{{font-size:clamp(27px,4vw,40px);line-height:1.2;font-weight:400;margin:8px 0 20px}}.details,.related{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:22px}}.detail,.related a{{padding:17px 19px;border:1px solid var(--line);background:var(--surface)}}.detail b{{display:block;color:var(--gold);font:600 14px Arial,sans-serif;margin-bottom:6px}}.detail span{{font-size:17px;color:var(--muted)}}.related a{{display:block;text-decoration:none;font-size:17px}}
.purchase{{padding:48px 0 60px;text-align:center;border-top:1px solid var(--line)}}.purchase p{{max-width:760px;margin:0 auto 22px;color:var(--muted);font-size:18px}}.trust{{font:13px/1.8 Arial,sans-serif;color:var(--muted);margin-top:16px}}footer{{border-top:1px solid var(--line);padding:24px 0 34px;display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;color:var(--muted);font:12px Arial,sans-serif}}
[dir="rtl"]{{text-align:right}}a:focus-visible,select:focus-visible{{outline:3px solid var(--gold);outline-offset:4px}}
@media(max-width:680px){{.shell{{width:calc(100% - 28px)}}header{{padding:12px 0;min-height:68px}}.hero{{padding:20px 0 34px}}.art-wrap{{margin-bottom:25px;padding:9px}}.summary,.description,.copy{{font-size:18px;line-height:1.85}}.details,.related{{grid-template-columns:1fr}}.price-line{{align-items:stretch;flex-direction:column}}.buy{{width:100%}}footer{{flex-direction:column}}}}
@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{scroll-behavior:auto!important;transition:none!important;animation:none!important}}}}
</style></head><body><div class="shell">
<header><a class="brand" href="https://alshayebemad.gumroad.com/">HALL OF <span>GREATNESS</span></a><div class="controls"><label for="lang" id="languageLabel">Choose language</label><select id="lang" aria-label="Choose language"></select></div></header>
<main><section class="hero"><div class="art-wrap"><img class="art" src="{cover}" alt="{name} cover" loading="eager"></div><div class="hero-copy"><div class="kicker">{kind} · HALL OF GREATNESS</div><h1 id="productTitle">{name}</h1><div class="subtitle" id="subtitle"></div><p class="summary" id="summary">{summary}</p><div class="price-line"><div class="price" data-gumroad-field="price"></div><a class="buy" href="#" data-gumroad-action="buy" id="buy">Get this digital product</a></div><p class="fine" id="delivery">Instant digital delivery after purchase. Please review the product details before purchase.</p></div></section>
<section class="section"><div class="section-inner"><div class="kicker" id="storyLabel">THE STORY</div><h2 id="storyTitle">The meaning behind this product</h2><div class="description" id="fullDescription"></div></div></section>
<section class="section"><div class="section-inner"><div class="kicker" id="detailsLabel">PRODUCT DETAILS</div><h2 id="detailsTitle">What you should know</h2><div class="details" id="details"></div></div></section>
<section class="section"><div class="section-inner"><div class="kicker" id="relatedLabel">EXPLORE MORE</div><h2 id="relatedTitle">More from HALL OF GREATNESS</h2><div class="related" id="related"></div></div></section>
<section class="purchase"><div class="kicker" id="purchaseLabel">MAKE IT YOURS</div><h2 id="purchaseTitle">Bring this story into your world.</h2><p id="purchaseText">{summary}</p><div class="price" data-gumroad-field="price"></div><a class="buy" href="#" data-gumroad-action="buy" id="buyBottom">Get this digital product</a><div class="trust">Secure checkout through Gumroad · Instant digital delivery</div><div class="trust" data-gumroad-field="rating"></div><div class="trust" data-gumroad-field="review-count"></div></section></main>
<footer><span>HALL OF GREATNESS</span><span>Art with a Soul. A Message Without Borders.</span></footer></div>
<script>const DATA=__DATA__;const LANGS=__LANGS__;const WORDS={{en:["Choose language","Get this digital product","Instant digital delivery after purchase. Please review the product details before purchase.","THE STORY","The meaning behind this product","PRODUCT DETAILS","What you should know","EXPLORE MORE","More from HALL OF GREATNESS","MAKE IT YOURS","Bring this story into your world."],ar:["اختر اللغة","احصل على المنتج الرقمي","تنزيل رقمي فوري بعد الشراء. يرجى مراجعة تفاصيل المنتج قبل إتمام الشراء.","الحكاية","المعنى وراء هذا المنتج","تفاصيل المنتج","معلومات مهمة قبل الشراء","اكتشف المزيد","المزيد من HALL OF GREATNESS","اجعله جزءاً من عالمك","دع هذه الحكاية تجد مكانها في عالمك."],fr:["Choisir la langue","Obtenir ce produit numérique","Téléchargement numérique instantané après l'achat.","L'HISTOIRE","Le sens de ce produit","DÉTAILS DU PRODUIT","À savoir avant l'achat","DÉCOUVRIR PLUS","Plus de HALL OF GREATNESS","FAITES-LE VÔTRE","Faites entrer cette histoire dans votre univers."]}};const DETAIL={{en:["Product type","Delivery","Physical item","Printing","Usage","Files included","Collection contents"],ar:["نوع المنتج","التسليم","المنتج المادي","الطباعة","الاستخدام","الملفات المرفقة","محتويات المجموعة"],fr:["Type de produit","Livraison","Article physique","Impression","Utilisation","Fichiers inclus","Contenu de la collection"]}};const KEYS=["product_type","delivery","physical_item","printing","usage","files_included","bundle_item_count"];const select=document.getElementById("lang");LANGS.forEach(x=>{{const o=document.createElement("option");o.value=x.code;o.textContent=x.name;select.appendChild(o)}});function setLanguage(code){{const t=DATA.translations[code]||DATA.translations.en;const w=WORDS[code]||WORDS.en;const labels=DETAIL[code]||DETAIL.en;document.documentElement.lang=code;document.documentElement.dir=["ar","fa","he","ur"].includes(code)?"rtl":"ltr";document.getElementById("languageLabel").textContent=w[0];document.getElementById("buy").textContent=w[1];document.getElementById("buyBottom").textContent=w[1];document.getElementById("delivery").textContent=w[2];document.getElementById("storyLabel").textContent=w[3];document.getElementById("storyTitle").textContent=w[4];document.getElementById("detailsLabel").textContent=w[5];document.getElementById("detailsTitle").textContent=w[6];document.getElementById("relatedLabel").textContent=w[7];document.getElementById("relatedTitle").textContent=w[8];document.getElementById("purchaseLabel").textContent=w[9];document.getElementById("purchaseTitle").textContent=w[10];document.getElementById("productTitle").textContent=t.name;document.getElementById("summary").textContent=t.summary;document.getElementById("purchaseText").textContent=t.summary;document.getElementById("fullDescription").textContent=t.full_description;const box=document.getElementById("details");box.replaceChildren();Object.entries(t.details||{{}}).forEach(([k,v])=>{{if(!v)return;const i=document.createElement("div");i.className="detail";const b=document.createElement("b");const idx=KEYS.indexOf(k);b.textContent=idx>=0?labels[idx]:k.replace(/_/g," ");const s=document.createElement("span");s.textContent=v;i.append(b,s);box.append(i)}});const rel=document.getElementById("related");rel.replaceChildren();DATA.related.forEach(x=>{{const a=document.createElement("a");a.href=x.url;a.target="_blank";a.rel="noopener noreferrer";a.textContent=x.name;rel.append(a)}})}}select.addEventListener("change",()=>setLanguage(select.value));setLanguage("en");</script></body></html>"""
    return page.replace("__DATA__",js(data)).replace("__LANGS__",js(languages))
generated=[]
for p in products:
    path=ROOT/"gumroad-landings"/slug(p.get("landing_slug") or p["name"])/"landing.html"
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(render(p),encoding="utf-8")
    generated.append({"permalink":p["permalink"],"name":p["name"],"file":str(path.relative_to(ROOT))})
(EVIDENCE/"generated-pages.json").write_text(json.dumps(generated,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("Generated",len(generated),"published product pages.")
outcomes=[]
for x in generated:
    key=x["permalink"]; path=x["file"]
    r=subprocess.run(["gumroad","products","page","preview",key,path,"--json","--no-input","--non-interactive"],cwd=ROOT,env=ENV,text=True,capture_output=True)
    if r.returncode:
        outcomes.append({"permalink":key,"status":"preview_error","error":(r.stderr or r.stdout)[-1200:]}); break
    try: report=json.loads(r.stdout).get("sanitization_report")
    except Exception: report=None
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
