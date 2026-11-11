(function(){
"use strict";
const body=document.body, permalink=body.dataset.productPermalink||"";
const select=document.getElementById("hog-page-language");
let registry=[];
const originalTextNodes=[];
const walker=document.createTreeWalker(body,NodeFilter.SHOW_TEXT);
while(walker.nextNode())originalTextNodes.push({node:walker.currentNode,original:walker.currentNode.nodeValue});
const closingButton=document.querySelector(".closing .btn");
const closingButtonOriginal=closingButton?closingButton.textContent:"";
async function init(){
 try{const r=await fetch("../../locales/languages.json");if(r.ok)registry=(await r.json()).languages||[];}catch(e){}
 if(select&&registry.length)select.innerHTML='<option value="auto">🌐 Auto</option>'+registry.map(x=>'<option value="'+x.code+'">'+x.name+'</option>').join("");
 const saved=(()=>{try{return localStorage.getItem("hog-language")}catch(e){return null}})();
 const auto=()=>{for(const l of (navigator.languages||[navigator.language||"en"])){const exact=registry.find(x=>x.code.toLowerCase()===l.toLowerCase());if(exact)return exact.code;const base=l.split("-")[0];const match=registry.find(x=>x.code===base);if(match)return match.code;}return "en";};
 async function apply(code){
  const lang=code==="auto"?auto():code;let data={};
  if(lang!=="en"){try{const r=await fetch("../../locales/"+encodeURIComponent(lang)+".json");if(r.ok)data=await r.json();}catch(e){}}
  const p=(data.products||{})[permalink]||{};
  const pageCopy=(data.landing_pages||{})[permalink]||{};
  const landing={...(data.landing_ui||{}),...pageCopy};
  originalTextNodes.forEach(({node,original})=>{if(node.isConnected){let value=original;Object.entries(landing).forEach(([source,translated])=>{if(source!=="Get"&&source&&value.includes(source))value=value.split(source).join(translated);});node.nodeValue=value;}});
  document.documentElement.lang=lang;
  const rtl=(registry.find(x=>x.code===lang)||{}).rtl||false;
  document.documentElement.dir=rtl?"rtl":"ltr";
  if(p.full_description){const box=document.querySelector("[data-hog-full-description]");if(box){box.querySelectorAll(":scope > p").forEach(el=>el.remove());p.full_description.split(/\n\s*\n/).filter(Boolean).forEach(t=>{const el=document.createElement("p");el.textContent=t;box.appendChild(el);});}}
  if(p.product_details){const box=document.querySelector("[data-hog-product-details]");if(box){const labels=data.product_detail_labels||{};box.querySelectorAll(":scope > p").forEach(el=>el.remove());Object.entries(p.product_details).forEach(([k,v])=>{if(!v)return;const el=document.createElement("p"),strong=document.createElement("strong");strong.textContent=(labels[k]||k.replace(/_/g," "))+": ";el.append(strong,document.createTextNode(v));box.appendChild(el);});}}
  if(p.summary){document.querySelectorAll("[data-hog-summary]").forEach(el=>el.textContent=p.summary);}
  if(p.category){document.querySelectorAll("[data-hog-category]").forEach(el=>el.textContent=p.category);}
  if(closingButton&&closingButtonOriginal){const prefix=landing["Get"]||"Get";closingButton.textContent=/^Get\s/.test(closingButtonOriginal)?prefix+closingButtonOriginal.slice(3):closingButtonOriginal;}
  if(select)select.value=code;
 }
 const initial=saved||"auto";await apply(initial);
 if(select)select.addEventListener("change",()=>{const v=select.value;try{if(v==="auto")localStorage.removeItem("hog-language");else localStorage.setItem("hog-language",v)}catch(e){}apply(v);});
}
if(select)init();
})();