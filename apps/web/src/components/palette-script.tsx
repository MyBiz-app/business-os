/** Sets the remembered palette (components/palette.tsx) before the first paint, so the page
 * never flashes another one. Rendered once in the root layout's <head>. */
export function PaletteScript() {
  const code = `try{var p=localStorage.getItem("palette");if(p==="ocean"||p==="forest")document.documentElement.dataset.palette=p}catch(e){}`;
  return <script dangerouslySetInnerHTML={{ __html: code }} />;
}
