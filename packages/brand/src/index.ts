/**
 * The MyBiz logo in one place: its colors and the geometry of its mark. The product name is not
 * here: it comes from `BRAND.name` in `@business-os/i18n/brand` (its single home). Every logo file (web
 * favicon, app icons, wordmarks) is drawn from these values and that name by
 * `pnpm --filter @business-os/brand build:assets`, and the web draws the mark from them inline,
 * so recoloring or renaming is a change in one place plus one script run.
 */

/** The logo gradient, top-left to bottom-right: violet, blue, sky. */
export const LOGO_GRADIENT = ["#7C3AED", "#3B82F6", "#0EA5E9"] as const;

/** Wordmark text on light and on dark surfaces. */
export const LOGO_INK = { light: "#0F172A", dark: "#F8FAFC" } as const;

/**
 * The mark: an M drawn as a network of five nodes, on a 64 x 64 grid.
 * The tile is the rounded square behind it; app icons that the system masks use the square edge.
 */
export const MARK = {
  size: 64,
  tileRadius: 15,
  path: "M18 43V22L32 36L46 22V43",
  strokeWidth: 5.5,
  nodes: [
    [18, 22],
    [32, 36],
    [46, 22],
    [46, 43],
    [18, 43],
  ],
  nodeRadius: 4.2,
  nodeCoreRadius: 1.7,
} as const;

/** An SVG gradient definition with the logo colors; by default top-left to bottom-right of its shape. */
export function gradient(id: string, direction = 'x1="0" y1="0" x2="1" y2="1"'): string {
  const stops = LOGO_GRADIENT.map(
    (color, i) => `<stop offset="${(i / (LOGO_GRADIENT.length - 1)) * 100}%" stop-color="${color}"/>`,
  ).join("");
  return `<linearGradient id="${id}" ${direction}>${stops}</linearGradient>`;
}

/** The M with its nodes. `ink` colors the lines, `core` the dot inside each node (none for one color). */
export function glyph({ ink, core }: { ink: string; core: string | null }): string {
  const nodes = MARK.nodes
    .map(
      ([x, y]) =>
        `<circle cx="${x}" cy="${y}" r="${MARK.nodeRadius}" fill="${ink}"/>` +
        (core ? `<circle cx="${x}" cy="${y}" r="${MARK.nodeCoreRadius}" fill="${core}"/>` : ""),
    )
    .join("");
  return `<path d="${MARK.path}" stroke="${ink}" stroke-width="${MARK.strokeWidth}" stroke-linecap="round" stroke-linejoin="round" fill="none"/>${nodes}`;
}

/** The mark as a standalone SVG: gradient tile with a white M. `radius` 0 gives a full square. */
export function markSvg({ radius = MARK.tileRadius, scale = 1 }: { radius?: number; scale?: number } = {}): string {
  const s = MARK.size;
  const inset = (s - s * scale) / 2;
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${s} ${s}" fill="none"><defs>${gradient("g")}</defs>` +
    `<rect width="${s}" height="${s}" rx="${radius}" fill="url(#g)"/>` +
    `<g transform="translate(${inset} ${inset}) scale(${scale})">${glyph({ ink: "#FFFFFF", core: "url(#g)" })}</g></svg>`
  );
}
