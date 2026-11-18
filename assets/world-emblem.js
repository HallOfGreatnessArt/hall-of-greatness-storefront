/* Sequential flag presentation: each flag remains centered for a full 3 seconds. */
(()=>{
 const mount=document.querySelector("[data-hog-world-emblem]");
 if(!mount||mount.dataset.ready==="true")return;
 mount.dataset.ready="true";
 const countries=[
  ["eg","Egypt"],["gb","United Kingdom"],["us","United States"],["fr","France"],
  ["de","Germany"],["it","Italy"],["es","Spain"],["pt","Portugal"],
  ["gr","Greece"],["in","India"],["jp","Japan"],["cn","China"],
  ["kr","South Korea"],["ca","Canada"],["au","Australia"],["br","Brazil"],
  ["mx","Mexico"],["sa","Saudi Arabia"],["ae","United Arab Emirates"],["tr","Türkiye"],
  ["se","Sweden"],["no","Norway"],["ch","Switzerland"],["za","South Africa"]
 ];
 const orbit=mount.querySelector(".hog-orbit");
 const reduced=window.matchMedia("(prefers-reduced-motion: reduce)").matches;
 const flags=[];
 const size=mount.getBoundingClientRect().width;
 const radius=size*.365;
 countries.forEach(([code,name],i)=>{
  const angle=(i/countries.length)*Math.PI*2-Math.PI/2;
  const x=size/2+Math.cos(angle)*radius;
  const y=size/2+Math.sin(angle)*radius;
  const img=document.createElement("img");
  img.className="hog-orbit-flag";
  img.src="https://flagcdn.com/w80/"+code+".png";
  img.alt=name+" flag";
  img.loading="eager";
  img.decoding="async";
  img.style.left=x+"px";
  img.style.top=y+"px";
  orbit.appendChild(img);
  flags.push({code,name,x:x-size/2,y:y-size/2});
 });
 const wait=ms=>new Promise(resolve=>window.setTimeout(resolve,ms));
 let index=0;
 let active=null;
 const showNext=async()=>{
  const flag=flags[index%flags.length];
  const img=document.createElement("img");
  img.className="hog-active-flag";
  img.src="https://flagcdn.com/w640/"+flag.code+".png";
  img.alt=flag.name+" flag";
  img.setAttribute("role","img");
  img.style.setProperty("--hog-from-x",flag.x+"px");
  img.style.setProperty("--hog-from-y",flag.y+"px");
  mount.appendChild(img);
  active=img;
  if(reduced)img.classList.add("is-center");
  else requestAnimationFrame(()=>requestAnimationFrame(()=>img.classList.add("is-center")));
  index++;
  await wait(reduced?0:600);
  if(active!==img)return;
  await wait(3000);
  if(active!==img)return;
  img.classList.remove("is-center");
  img.classList.add("is-returning");
  await wait(reduced?0:600);
  img.remove();
  if(active===img)active=null;
  showNext();
 };
 showNext();
 document.addEventListener("visibilitychange",()=>{
  if(document.hidden&&active)active.style.transition="none";
  else if(active)active.style.transition="";
 });
})();