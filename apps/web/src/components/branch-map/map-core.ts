import type { Map as MapLibreMap } from "maplibre-gl";

/** The map library, told where its worker is (see scripts/copy-maplibre-worker.mjs). */
export async function loadMaplibre() {
  const maplibre = await import("maplibre-gl");
  maplibre.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
  return maplibre;
}

/** Free vector styles from OpenFreeMap (OpenStreetMap data, no key, no sign-up). */
const STYLES = {
  light: "https://tiles.openfreemap.org/styles/positron",
  dark: "https://tiles.openfreemap.org/styles/dark",
} as const;

export type MapTone = keyof typeof STYLES;

export const styleUrl = (tone: MapTone) => STYLES[tone];

/** The page's current theme (the `dark` class on <html>). */
export const currentTone = (): MapTone => (document.documentElement.classList.contains("dark") ? "dark" : "light");

export const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Re-skins the map whenever the person switches between light and dark. */
export function followTheme(map: MapLibreMap): () => void {
  let tone = currentTone();
  const observer = new MutationObserver(() => {
    const next = currentTone();
    if (next === tone) return;
    tone = next;
    map.setStyle(styleUrl(next));
  });
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

/** The ratio of `value` to the largest of `values`, 0 when there is nothing to compare. */
export function share(value: number | null, values: (number | null)[]): number {
  const max = Math.max(0, ...values.map((v) => v ?? 0));
  return max > 0 && value ? Math.min(1, value / max) : 0;
}
