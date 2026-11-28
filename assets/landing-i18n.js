(function(){
"use strict";
const body=document.body, permalink=body.dataset.productPermalink||"";
const select=document.getElementById("hog-page-language");
let registry=[];
async function init(){
 try{const r=await fetch("../../locales/languages.json");if(r.ok)registry=((await r.json()).languages||[]).filter(x=>x.code==="en"||x.available!==false);}catch(e){}
 if(select&&registry.length)select.innerHTML='<option value="auto">🌐 Auto</option>'+registry.map(x=>'<option value="'+x.code+'">'+x.name+'</option>').join("");
 const saved=(()=>{try{return localStorage.getItem("hog-language")}catch(e){return null}})();
 const auto=()=>{for(const l of (navigator.languages||[navigator.language||"en"])){const exact=registry.find(x=>x.code.toLowerCase()===l.toLowerCase());if(exact)return exact.code;const base=l.split("-")[0];const match=registry.find(x=>x.code===base);if(match)return match.code;}return "en";};
 async function apply(code){
  const lang=code==="auto"?auto():code;let data={};
  if(lang!=="en"){try{const r=await fetch("../../locales/"+encodeURIComponent(lang)+".json");if(r.ok)data=await r.json();}catch(e){}}
  const restoreSelectors=["[data-hog-title]","[data-hog-subtitle]","[data-hog-summary]","[data-hog-category]",".hero .btn",".closing .btn",".note",".price span","#full-description","#product-details","#reading-experience","#digital-delivery","#learning-experience","#course-access",".experience-points","#printing .eyebrow","#printing h2",".print-step b",".print-step p",".digital-reminder",".room-showcase .eyebrow",".room-showcase h2",".room-showcase .room-intro p",".closing h2",".closing p",".purchase-chip"];
  restoreSelectors.forEach(selector=>document.querySelectorAll(selector).forEach(el=>{if(el.dataset.hogDefaultHtml===undefined)el.dataset.hogDefaultHtml=el.innerHTML;el.innerHTML=el.dataset.hogDefaultHtml;}));
  if(document.documentElement.dataset.hogDefaultTitle===undefined)document.documentElement.dataset.hogDefaultTitle=document.title;
  document.title=document.documentElement.dataset.hogDefaultTitle;
  const p=(data.products||{})[permalink]||{};
  const setText=(selector,value)=>{const el=document.querySelector(selector);if(el)el.textContent=value;};
  if(lang==="ar"){
   if(p.title_ar){const h=document.querySelector("[data-hog-title]");if(h)h.textContent=p.title_ar;document.title=p.title_ar+" | HALL OF GREATNESS";}
   const sub=document.querySelector("[data-hog-subtitle]");if(sub)sub.textContent="عمل فني رقمي أصيل من HALL OF GREATNESS";
   document.querySelectorAll(".hero .btn,.closing .btn").forEach((el,i)=>el.textContent=i===0?"استكشف واحصل على العمل الفني":"احصل على العمل الفني");
   document.querySelectorAll(".note").forEach(el=>el.textContent="دفع آمن وتسليم رقمي عبر Gumroad.");
   document.querySelectorAll(".price span").forEach(el=>el.textContent="· تنزيل رقمي");
   const setText=(selector,value)=>{const el=document.querySelector(selector);if(el)el.textContent=value;};
   setText("#full-description .eyebrow","حكاية العمل الفني");
   setText("#full-description h2","قصة العمل كاملة");
   setText("#product-details .eyebrow","محتويات التنزيل");
   setText("#product-details h2","مواصفات المنتج");
   setText("#printing .eyebrow","من التنزيل إلى العرض");
   setText("#printing h2","اجعل العمل الفني جزءاً من مساحتك");
   const steps=[["01 · الشراء","أتمم عملية الدفع الآمن عبر Gumroad. عملية الشراء تخص منتجاً رقمياً."],["02 · التنزيل","نزّل الملفات المتاحة لهذا المنتج وراجع المواصفات المرفقة."],["03 · الطباعة","اختر مقاساً يحافظ على النسب الأصلية للعمل، واستعن بمتخصص طباعة عند الحاجة."]];
   document.querySelectorAll(".print-step").forEach((el,i)=>{if(steps[i]){const b=el.querySelector("b"),p=el.querySelector("p");if(b)b.textContent=steps[i][0];if(p)p.textContent=steps[i][1];}});
   const reminder=document.querySelector(".digital-reminder");if(reminder)reminder.textContent="يرجى الانتباه: لن تُشحن لوحة مطبوعة أو إطار مادي. صيغ الملفات ودقتها وأبعادها وشروط استخدامها هي المحددة في ملفات المنتج والترخيص المرفق.";
   setText(".room-showcase .eyebrow","عرض العمل الفني");
   setText(".room-showcase h2","تخيّل العمل داخل إطار أنيق");
   const room=document.querySelector(".room-showcase .room-intro p");if(room)room.textContent="معاينة تساعدك على تخيل العمل الفني في إطار، مع الحفاظ على أبعاده ونسبه الأصلية.";
   setText(".closing h2","دع مساحتك تروي حكاية");
   const closing=document.querySelector(".closing p");if(closing)closing.textContent="اختر فناً يعبر عما تقدّره، ودع معناه يرافق تفاصيل المكان.";
   document.querySelectorAll(".purchase-chip").forEach((el,i)=>{const values=[["تنزيل رقمي","احصل على ملفاتك بعد إتمام الشراء"],["اطبع بطريقتك","اختر المقاس الملائم لمساحتك"],["فن يستحق العرض","للمنازل والاستوديوهات والمساحات ذات المعنى"]][i];if(values){const strong=document.createElement("strong");strong.textContent=values[0];el.replaceChildren(strong,document.createTextNode(values[1]));}});
  }
  if(lang==="ar" && body.dataset.contentType==="ebook"){
   const sub=document.querySelector("[data-hog-subtitle]");if(sub)sub.textContent="كتاب رقمي من HALL OF GREATNESS";
   const cat=document.querySelector("[data-hog-category]");if(cat)cat.textContent="كتاب إلكتروني · HALL OF GREATNESS";
   document.querySelectorAll(".hero .btn,.closing .btn").forEach((el,i)=>el.textContent=i===0?"استكشف الكتاب الإلكتروني":"احصل على الكتاب");
   setText(".closing h2","افتح آفاقاً جديدة بالمعرفة");
   const closing=document.querySelector(".closing p");if(closing)closing.textContent="ابدأ رحلة قراءة توسّع فهمك وتمنحك أفكاراً تستحق التأمل والتطبيق.";
   setText("#full-description .eyebrow","محتوى الكتاب");
   setText("#full-description h2","عن هذا الكتاب");
   setText("#product-details .eyebrow","تفاصيل النسخة الرقمية");
   setText("#product-details h2","مواصفات الكتاب");
   setText("#reading-experience .eyebrow","تجربة قراءة ثرية");
   setText("#reading-experience h2","أفكار تستحق الفهم ومعرفة تستحق الاحتفاظ بها");
   const bookPoints=[["اقرأ وفق وتيرتك","استمتع بكتابك الرقمي على الأجهزة وتطبيقات القراءة المتوافقة."],["معرفة تتجاوز الصفحات","استخدم أفكار الكتاب وموارده المرفقة مرجعاً للتعلم والتأمل."],["وصول رقمي فوري","نزّل الملفات المرفقة بهذه النسخة بعد إتمام الشراء عبر Gumroad."]];
   document.querySelectorAll("#reading-experience .experience-points>div").forEach((el,i)=>{if(bookPoints[i]){const b=el.querySelector("strong"),p=el.querySelector("p");if(b)b.textContent=bookPoints[i][0];if(p)p.textContent=bookPoints[i][1];}});
   setText("#digital-delivery .eyebrow","نسختك الرقمية");
   setText("#digital-delivery h2","اشترِ، نزّل، وابدأ القراءة");
   setText("#digital-delivery p","بعد إتمام الشراء، يمكنك الوصول إلى الملفات المرفقة بهذا المنتج عبر Gumroad. لن يتم شحن كتاب ورقي. راجع صيغ الملفات واللغة وبيانات الإصدار وشروط الاستخدام الموضحة في مواصفات المنتج والترخيص المرفق.");
  }
  if(lang==="ar" && body.dataset.contentType==="course"){
   const sub=document.querySelector("[data-hog-subtitle]");if(sub)sub.textContent="تجربة تعليمية من HALL OF GREATNESS";
   const cat=document.querySelector("[data-hog-category]");if(cat)cat.textContent="دورة تعليمية · HALL OF GREATNESS";
   document.querySelectorAll(".hero .btn,.closing .btn").forEach((el,i)=>el.textContent=i===0?"استكشف الدورة":"ابدأ رحلة التعلم");
   setText(".closing h2","ابدأ خطوتك التالية في التعلم");
   const closing=document.querySelector(".closing p");if(closing)closing.textContent="اختر تجربة تعليمية تدعم أهدافك وتساعدك على اكتساب معرفة ومهارات جديدة.";
   setText("#full-description .eyebrow","محتوى الدورة");
   setText("#full-description h2","ماذا ستتعلم؟");
   setText("#product-details .eyebrow","تفاصيل الدورة");
   setText("#product-details h2","المحتوى ومتطلبات الوصول");
   setText("#learning-experience .eyebrow","تجربة تعلم موجهة");
   setText("#learning-experience h2","تعلّم بوضوح، وطبّق المعرفة عملياً");
   const coursePoints=[["مسار تعلم واضح","تعرّف على الموضوعات والنتائج التعليمية التي تقدمها الدورة."],["تعلّم وفق وتيرتك","استخدم الدروس والمواد المتاحة وفق شروط الوصول المحددة للدورة."],["حوّل المعرفة إلى ممارسة","اربط ما تتعلمه بالأسئلة أو التدريبات أو المشروعات العملية عند توفرها."]];
   document.querySelectorAll("#learning-experience .experience-points>div").forEach((el,i)=>{if(coursePoints[i]){const b=el.querySelector("strong"),p=el.querySelector("p");if(b)b.textContent=coursePoints[i][0];if(p)p.textContent=coursePoints[i][1];}});
   setText("#course-access .eyebrow","الوصول إلى الدورة");
   setText("#course-access h2","سجّل، ابدأ، وتقدّم");
   setText("#course-access p","تُقدّم تعليمات الوصول إلى الدورة وموادها عبر صفحة المنتج ومواد الشراء. راجع المتطلبات والصيغة والمدة وشروط الوصول قبل الشراء. لا تُشحن مواد تعليمية مادية ما لم يُذكر ذلك صراحة.");
  }
  document.documentElement.lang=lang;
  const rtl=(registry.find(x=>x.code===lang)||{}).rtl||false;
  document.documentElement.dir=rtl?"rtl":"ltr";
  if(p.summary){document.querySelectorAll("[data-hog-summary]").forEach(el=>el.textContent=p.summary);}
  if(p.category){document.querySelectorAll("[data-hog-category]").forEach(el=>el.textContent=p.category);}
  if(p.full_description){const box=document.querySelector("[data-hog-full-description]");if(box){box.querySelectorAll(":scope > p").forEach(el=>el.remove());p.full_description.split(/\n\s*\n/).filter(Boolean).forEach(t=>{const el=document.createElement("p");el.textContent=t;box.appendChild(el);});}}
  if(p.product_details){const box=document.querySelector("[data-hog-product-details]");if(box){box.querySelectorAll(":scope > p").forEach(el=>el.remove());const labels=lang==="ar"?{files_included:"الملفات المرفقة",product_type:"نوع المنتج",delivery:"التسليم",physical_item:"المنتج المادي",printing:"الطباعة",usage:"الاستخدام والترخيص",bundle_item_count:"محتويات المجموعة"}:{};Object.entries(p.product_details).forEach(([k,v])=>{if(!v)return;const el=document.createElement("p"),strong=document.createElement("strong");strong.textContent=(labels[k]||k.replace(/_/g," "))+": ";el.append(strong,document.createTextNode(v));box.appendChild(el);});}}
  if(lang==="ar" && body.dataset.contentType==="ebook"){const cat=document.querySelector("[data-hog-category]");if(cat)cat.textContent="كتاب إلكتروني · HALL OF GREATNESS";}
  if(lang==="ar" && body.dataset.contentType==="course"){const cat=document.querySelector("[data-hog-category]");if(cat)cat.textContent="دورة تعليمية · HALL OF GREATNESS";}
  if(select)select.value=code;
 }
 const initial=(saved&&saved!=="auto"&&!registry.some(x=>x.code===saved))?"auto":(saved||"auto");await apply(initial);
 if(select)select.addEventListener("change",()=>{const v=select.value;try{if(v==="auto")localStorage.removeItem("hog-language");else localStorage.setItem("hog-language",v)}catch(e){}apply(v);});
}
if(select)init();
})();