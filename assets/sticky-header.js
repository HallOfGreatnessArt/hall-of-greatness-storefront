/* Keep the complete gallery header available as one compact navigation unit. */
(()=>{
 const header=document.querySelector(".wrap>header");
 if(!header)return;
 const threshold=120;
 let scheduled=false;
 const update=()=>{
  const compact=window.scrollY>threshold;
  header.classList.toggle("is-compact",compact);
  header.dataset.compact=compact?"true":"false";
  /* Language and navigation remain visible and accessible in both states. */
  header.querySelectorAll(".header-tools,#language-select,nav").forEach(el=>{
   el.setAttribute("aria-hidden","false");
  });
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