/* Keep the complete gallery header visible without shifting document layout. */
(()=>{
 const header=document.querySelector(".wrap>header");
 if(!header)return;
 const threshold=120;
 let compact=false,scheduled=false,preserveFlow=false,fullHeight=0,targetHeight=0;
 const spacer=document.createElement("div");
 spacer.className="hog-header-flow-spacer";
 spacer.setAttribute("aria-hidden","true");
 spacer.setAttribute("role","presentation");
 header.insertAdjacentElement("afterend",spacer);
 const height=()=>header.getBoundingClientRect().height;
 const setSpacer=()=>{spacer.style.height=preserveFlow?Math.max(0,fullHeight-height())+"px":"0px";};
 const naturalHeight=()=>{
  const prior=header.style.height;
  header.style.height="auto";
  const measured=height();
  header.style.height=prior;
  return measured;
 };
 const finish=()=>{
  const now=height();
  if(compact){
   targetHeight=now;
   header.style.height=now+"px";
   preserveFlow=true;
   setSpacer();
  }else{
   fullHeight=now;
   header.style.height="";
   preserveFlow=false;
   spacer.style.height="0px";
  }
 };
 const transitionTo=(next)=>{
  if(next===compact)return;
  const current=height();
  if(!compact)fullHeight=current;
  preserveFlow=true;
  header.style.height=current+"px";
  header.classList.toggle("is-compact",next);
  targetHeight=naturalHeight();
  compact=next;
  setSpacer();
  requestAnimationFrame(()=>{header.style.height=targetHeight+"px";setSpacer();});
 };
 header.addEventListener("transitionend",event=>{
  if(event.target===header&&event.propertyName==="height")finish();
 });
 const observer=new ResizeObserver(()=>{
  if(!compact&&!preserveFlow)fullHeight=height();
  else setSpacer();
 });
 observer.observe(header);
 const update=()=>{
  const next=window.scrollY>threshold;
  transitionTo(next);
  header.dataset.compact=next?"true":"false";
  header.querySelectorAll(".header-tools,#language-select,nav").forEach(el=>el.setAttribute("aria-hidden","false"));
  scheduled=false;
 };
 const onScroll=()=>{
  if(scheduled)return;
  scheduled=true;
  requestAnimationFrame(update);
 };
 window.addEventListener("scroll",onScroll,{passive:true});
 window.addEventListener("resize",()=>{
  if(!compact){fullHeight=height();return;}
  const current=height();
  header.style.height="auto";
  targetHeight=height();
  header.style.height=current+"px";
  requestAnimationFrame(()=>{header.style.height=targetHeight+"px";setSpacer();});
 },{passive:true});
 fullHeight=height();
 update();
})();