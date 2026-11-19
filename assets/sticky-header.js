/* Keep the gallery identity visible while the visitor browses the storefront. */
(()=>{
 const header=document.querySelector(".wrap>header");
 if(!header)return;
 const threshold=120;
 const controls=header.querySelector(".header-tools");
 const language=header.querySelector("#language-select");
 const navigation=header.querySelector("nav");
 let scheduled=false;
 const update=()=>{
  const compact=window.scrollY>threshold;
  header.classList.toggle("is-compact",compact);
  header.dataset.compact=compact?"true":"false";
  if(controls){controls.setAttribute("aria-hidden",compact?"true":"false");}
  if(language){language.setAttribute("aria-hidden",compact?"true":"false");}
  if(navigation){navigation.setAttribute("aria-hidden",compact?"true":"false");}
  scheduled=false;
 };
 const onScroll=()=>{
  if(scheduled)return;
  scheduled=true;
  window.requestAnimationFrame(update);
 };
 window.addEventListener("scroll",onScroll,{passive:true});
 window.addEventListener("resize",onScroll,{passive:true});
 update();
})();