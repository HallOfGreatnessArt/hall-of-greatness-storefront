/* The gallery header has one permanent compact layout; scrolling never resizes it. */
(()=>{
 const header=document.querySelector(".wrap>header");
 if(!header)return;
 header.dataset.layout="fixed-compact";
 header.classList.remove("is-compact");
 header.style.removeProperty("height");
 const spacer=document.querySelector(".hog-header-flow-spacer");
 if(spacer)spacer.remove();
})();