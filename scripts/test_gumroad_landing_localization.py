#!/usr/bin/env python3
"""Browser QA for Gumroad product landing localization using the gallery locale data."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
BASE="http://127.0.0.1:8000/gumroad-landings"
CAT=json.loads((ROOT/"catalog-data.json").read_text(encoding="utf-8"))
COPY=json.loads((ROOT/"ebook-copy.json").read_text(encoding="utf-8"))
REG=json.loads((ROOT/"locales/languages.json").read_text(encoding="utf-8"))["languages"]
REG_BY_CODE={x["code"]:x for x in REG}

def check(value,message):
    if not value: raise AssertionError(message)

def expected_copy(product,code):
    key=product["permalink"]
    if product.get("content_type")=="ebook":
        if code=="en": return COPY[key]["en"]["overview"]
        if code=="ar": return COPY[key]["ar"]["overview"]
        locale=json.loads((ROOT/"locales"/(code+".json")).read_text(encoding="utf-8"))
        return locale["ebooks"][key]["overview"]
    if code=="en": return product.get("summary","")
    locale=json.loads((ROOT/"locales"/(code+".json")).read_text(encoding="utf-8"))
    return locale["products"][key]["summary"]

def main():
    products=[]
    for permalink in ("mxrljy","qsznm"):
        product=next(x for x in CAT["products"] if x.get("permalink")==permalink)
        products.append(product)
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for product in products:
            slug=product.get("landing_slug") or product["name"].lower().replace(" ","-")
            page=browser.new_page(viewport={"width":1440,"height":1000})
            errors=[]
            page.on("pageerror",lambda exc:errors.append(str(exc)))
            page.goto(f"{BASE}/{slug}/landing.html",wait_until="networkidle")
            page.locator("#lang").wait_for()
            options=page.locator("#lang option").evaluate_all("(nodes)=>nodes.map(x=>x.value)")
            check("en" in options and "ar" in options,f"{product['permalink']}: English/Arabic missing: {options}")
            for code in options:
                if code=="auto": continue
                page.select_option("#lang",code)
                entry=REG_BY_CODE.get(code,{"rtl":False})
                direction="rtl" if entry.get("rtl") else "ltr"
                page.wait_for_function("(x)=>document.documentElement.lang===x[0]&&document.documentElement.dir===x[1]",arg=[code,direction])
                expected=expected_copy(product,code)
                actual=page.locator("#summary").inner_text()
                check(actual==expected,f"{product['permalink']}/{code}: product summary differs from gallery locale source")
                check(len(actual.strip())>=20 and actual.strip() not in (".","..","..."),f"{product['permalink']}/{code}: placeholder summary leaked")
                check("nnnnnn" not in page.locator("body").inner_text().lower(),f"{product['permalink']}/{code}: repeated-character corruption leaked")
                check("share" not in page.locator("#fullDescription").inner_text().strip().splitlines()[0].lower(),f"{product['permalink']}/{code}: Gumroad Share control leaked into description")
                locale_ui=json.loads((ROOT/"locales"/(code+".json")).read_text(encoding="utf-8"))["ui"] if code!="en" else json.loads((ROOT/"locales/ar.json").read_text(encoding="utf-8"))["ui"]
                expected_buy=locale_ui["landingBuy"] if code!="en" else "Buy / download"
                check(page.locator("#buy").inner_text()==expected_buy,f"{product['permalink']}/{code}: localized purchase CTA mismatch")
            page.select_option("#lang","en")
            page.wait_for_function("document.documentElement.lang==='en'&&document.documentElement.dir==='ltr'")
            check(page.locator("#summary").inner_text()==expected_copy(product,"en"),f"{product['permalink']}: English copy did not restore")
            check(not errors,f"{product['permalink']}: browser errors: {errors}")
            print(f"PASS {product['permalink']}: {len(options)-1} validated language options, matching gallery copy, CTA, RTL/LTR, and no corrupted text")
            page.close()
        auto=browser.new_page(locale="ar-EG")
        auto.goto(f"{BASE}/the-art-of-stillness/landing.html",wait_until="networkidle")
        auto.wait_for_function("document.documentElement.lang==='ar'&&document.documentElement.dir==='rtl'")
        check(auto.locator("#lang").input_value()=="ar","Browser-language auto detection did not select Arabic")
        auto.select_option("#lang","ar")
        auto.reload(wait_until="networkidle")
        auto.wait_for_function("document.documentElement.lang==='ar'&&document.documentElement.dir==='rtl'")
        print("PASS browser-language detection and saved language preference")
        browser.close()

if __name__=="__main__":
    main()
