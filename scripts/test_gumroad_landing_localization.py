#!/usr/bin/env python3
"""Browser QA for Gumroad product landing localization using the gallery locale data."""
import argparse
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
BASE="http://127.0.0.1:8000/gumroad-landings"
CAT=json.loads((ROOT/"catalog-data.json").read_text(encoding="utf-8"))
COPY=json.loads((ROOT/"ebook-copy.json").read_text(encoding="utf-8"))
REG=json.loads((ROOT/"locales/languages.json").read_text(encoding="utf-8"))["languages"]
REG_BY_CODE={x["code"]:x for x in REG}
I18N=(ROOT/"assets/i18n.js").read_text(encoding="utf-8")
match=re.search(r"const M=(\{[\s\S]*?\});\nconst map=",I18N)
if not match: raise SystemExit("Canonical English UI dictionary not found")
CANONICAL=json.loads(match.group(1))
EN_UI=CANONICAL.get("en",{})

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
    parser=argparse.ArgumentParser(description="Targeted browser QA for Gumroad landing localization")
    parser.add_argument("--product", help="Optional single product permalink")
    parser.add_argument("--language", help="Optional single language code; omit to test every available language")
    args=parser.parse_args()
    products=[]
    permalinks=[args.product] if args.product else ["mxrljy","qsznm"]
    for permalink in permalinks:
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
            selected_codes=[args.language] if args.language else [code for code in options if code!="auto"]
            for code in selected_codes:
                check(code in options, f"{product['permalink']}: requested language {code} is not offered; options={options}")
                page.select_option("#lang",code)
                entry=REG_BY_CODE.get(code,{"rtl":False})
                direction="rtl" if entry.get("rtl") else "ltr"
                page.wait_for_function("(x)=>document.documentElement.lang===x[0]&&document.documentElement.dir===x[1]",arg=[code,direction])
                expected=expected_copy(product,code)
                actual=page.locator("#summary").inner_text()
                check(actual==expected,f"{product['permalink']}/{code}: product summary differs from gallery locale source")
                check(len(actual.strip())>=20 and actual.strip() not in (".","..","..."),f"{product['permalink']}/{code}: placeholder summary leaked")
                check("nnnnnn" not in page.locator("body").inner_text().lower(),f"{product['permalink']}/{code}: repeated-character corruption leaked")
                description_text=(page.locator("#fullDescription").text_content() or "").strip()
                description_lines=[line.strip() for line in description_text.splitlines() if line.strip()]
                check(bool(description_lines),f"{product['permalink']}/{code}: full product description is empty")
                check(description_lines[0].casefold() not in ("share","compartir","partager","поделиться"),f"{product['permalink']}/{code}: Gumroad Share control leaked into description")
                locale_ui=json.loads((ROOT/"locales"/(code+".json")).read_text(encoding="utf-8"))["ui"] if code!="en" else EN_UI
                expected_buy=locale_ui.get("landingBuy")
                actual_buy=page.locator("#buy").inner_text().strip()
                check(bool(expected_buy) and actual_buy==expected_buy, f"{product['permalink']}/{code}: localized purchase CTA mismatch (expected={expected_buy!r}, actual={actual_buy!r})")
            if not args.language or args.language=="en":
                page.select_option("#lang","en")
                page.wait_for_function("document.documentElement.lang==='en'&&document.documentElement.dir==='ltr'")
                check(page.locator("#summary").inner_text()==expected_copy(product,"en"),f"{product['permalink']}: English copy did not restore")
            check(not errors,f"{product['permalink']}: browser errors: {errors}")
            print(f"PASS {product['permalink']}: {len(options)-1} validated language options, matching gallery copy, CTA, RTL/LTR, and no corrupted text")
            page.close()
        if not args.product and not args.language:
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
