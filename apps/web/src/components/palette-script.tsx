/** Sets the remembered palette (components/palette.tsx) before the first paint, so the page
 * never flashes another one; also the reading choices of components/accessibility.tsx. Rendered once in the root layout's <head>. "My own colors" were
 * derived when they were last saved or edited and are kept whole in `palette-custom`. */
export function PaletteScript() {
  const code = `try{var d=document.documentElement,a=JSON.parse(localStorage.getItem("a11y"));if(a)for(var j in a)if(a[j]!=="normal")d.dataset[j]=a[j]}catch(e){}try{var d=document.documentElement,p=localStorage.getItem("palette");if(p==="ocean"||p==="forest")d.dataset.palette=p;else if(p==="custom"){var c=JSON.parse(localStorage.getItem("palette-custom"));if(c&&c.tokens){d.dataset.palette="custom";for(var k in c.tokens)d.style.setProperty(k,c.tokens[k]);d.classList.toggle("dark",c.scheme==="dark")}}}catch(e){}`;
  return <script dangerouslySetInnerHTML={{ __html: code }} />;
}
