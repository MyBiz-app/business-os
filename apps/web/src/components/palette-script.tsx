/** Sets the remembered palette (components/palette.tsx) before the first paint, so the page
 * never flashes another one. Rendered once in the root layout's <head>. "My own colors" were
 * derived when they were last saved or edited and are kept whole in `palette-custom`. */
export function PaletteScript() {
  const code = `try{var d=document.documentElement,p=localStorage.getItem("palette");if(p==="ocean"||p==="forest")d.dataset.palette=p;else if(p==="custom"){var c=JSON.parse(localStorage.getItem("palette-custom"));if(c&&c.tokens){d.dataset.palette="custom";for(var k in c.tokens)d.style.setProperty(k,c.tokens[k]);d.classList.toggle("dark",c.scheme==="dark")}}}catch(e){}`;
  return <script dangerouslySetInnerHTML={{ __html: code }} />;
}
