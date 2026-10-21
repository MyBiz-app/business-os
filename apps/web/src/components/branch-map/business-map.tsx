"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type { Map as MapLibreMap, Marker } from "maplibre-gl";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";

import { SegmentedControl } from "@/components/segmented-control";
import { CollapsibleSection } from "@/components/ui/collapsible-section";

import { currentTone, followTheme, loadMaplibre, styleUrl } from "./map-core";

export type BusinessMapCity = {
  code: number;
  name: string;
  latitude: number;
  longitude: number;
  total: number;
  /** `key` null: too few of one industry to name it (they are "mixed"). */
  industries: { key: string | null; total: number }[];
};

export type MapCategory = { key: string; label: string; color: string };

type Layer = "businesses" | "clients";

type Props = {
  layers: Record<Layer, BusinessMapCity[]>;
  categories: MapCategory[];
  minPerCity: number;
};

const MIXED = "var(--muted)";
const SMALL = 16;
const BIG = 54;

/** The MyBiz console's map: a dot per city, sized by how many businesses (or clients) are there
 * and colored by the leading industry. Totals only: a city with fewer than the minimum is never
 * sent here, so no business or person can be picked out. */
export function BusinessMap({ layers, categories, minPerCity }: Props) {
  const t = useTranslations("platform.businessMap");
  const locale = useLocale();
  const number = useMemo(() => new Intl.NumberFormat(locale), [locale]);
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markers = useRef<Marker[]>([]);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [layer, setLayer] = useState<Layer>("businesses");
  const [hovered, setHovered] = useState<BusinessMapCity | null>(null);

  const cities = layers[layer];
  const categoryOf = useMemo(() => new Map(categories.map((c) => [c.key, c])), [categories]);
  const mixedLabel = t("mixed");
  const industryName = (key: string | null) => (key ? (categoryOf.get(key)?.label ?? key) : mixedLabel);

  useEffect(() => {
    let cancelled = false;
    let stopTheme = () => {};
    (async () => {
      try {
        const maplibre = await loadMaplibre();
        if (cancelled || !container.current) return;
        const map = new maplibre.Map({
          container: container.current,
          style: styleUrl(currentTone()),
          center: [34.85, 31.5],
          zoom: 6,
          attributionControl: { compact: true },
          cooperativeGestures: true,
        });
        mapRef.current = map;
        map.addControl(new maplibre.NavigationControl({ showCompass: false }), "bottom-right");
        stopTheme = followTheme(map);
        setReady(true);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      stopTheme();
      for (const marker of markers.current) marker.remove();
      markers.current = [];
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  // The dots of the chosen layer.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    let cancelled = false;
    (async () => {
      const maplibre = await loadMaplibre();
      if (cancelled) return;
      for (const marker of markers.current) marker.remove();
      markers.current = [];
      const largest = Math.max(1, ...cities.map((c) => c.total));
      for (const city of cities) {
        const lead = city.industries.find((i) => i.key !== null)?.key ?? null;
        const dot = document.createElement("button");
        dot.type = "button";
        dot.className = "business-dot";
        const size = SMALL + Math.sqrt(city.total / largest) * (BIG - SMALL);
        dot.style.width = dot.style.height = `${size.toFixed(0)}px`;
        dot.style.background = lead ? (categoryOf.get(lead)?.color ?? MIXED) : MIXED;
        dot.setAttribute("aria-label", t("dot", { city: city.name, count: city.total }));
        dot.addEventListener("mouseenter", () => setHovered(city));
        dot.addEventListener("mouseleave", () => setHovered(null));
        dot.addEventListener("focus", () => setHovered(city));
        dot.addEventListener("blur", () => setHovered(null));
        markers.current.push(new maplibre.Marker({ element: dot }).setLngLat([city.longitude, city.latitude]).addTo(map));
      }
      if (cities.length > 1) {
        const bounds = new maplibre.LngLatBounds();
        for (const c of cities) bounds.extend([c.longitude, c.latitude]);
        map.fitBounds(bounds, { padding: 70, maxZoom: 9, duration: 0 });
      } else if (cities.length === 1) map.jumpTo({ center: [cities[0].longitude, cities[0].latitude], zoom: 9 });
    })();
    return () => {
      cancelled = true;
    };
  }, [ready, cities, categoryOf, t]);

  const present = useMemo(() => {
    const totals = new Map<string | null, number>();
    for (const city of cities) for (const i of city.industries) totals.set(i.key, (totals.get(i.key) ?? 0) + i.total);
    return [...totals.entries()].sort((a, b) => b[1] - a[1]);
  }, [cities]);

  const options: { value: Layer; label: string }[] = [
    { value: "businesses", label: t("layer.businesses") },
    { value: "clients", label: t("layer.clients") },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SegmentedControl label={t("layer.label")} value={layer} options={options} onChange={setLayer} />
        <p className="text-sm text-muted">{t("privacy", { min: minPerCity })}</p>
      </div>

      <div className="relative isolate h-[60vh] min-h-[24rem] overflow-hidden card">
        {/* MapLibre's own stylesheet makes the map element `position: relative`, so the sizing is on a wrapper. */}
        <div className="absolute inset-0">
          <div ref={container} className="size-full" role="region" aria-label={t("mapLabel")} />
        </div>
        {failed && <p className="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-muted">{t("failed")}</p>}
        {ready && cities.length === 0 && (
          <p role="status" className="pointer-events-none absolute inset-x-6 top-6 z-10 mx-auto max-w-md card p-4 text-center text-sm">
            {t(layer === "businesses" ? "emptyBusinesses" : "emptyClients", { min: minPerCity })}
          </p>
        )}
        {hovered && (
          <div role="status" className="pointer-events-none absolute end-3 top-3 z-10 flex w-60 flex-col gap-1 card p-3 text-sm">
            <span dir="auto" className="font-semibold">{hovered.name}</span>
            <span>{t(layer === "businesses" ? "hoverBusinesses" : "hoverClients", { count: number.format(hovered.total) })}</span>
            <ul className="flex flex-col gap-0.5 text-muted">
              {hovered.industries.map((i) => (
                <li key={i.key ?? "mixed"}>{t("industryRow", { industry: industryName(i.key), count: number.format(i.total) })}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {present.length > 0 && (
        <ul aria-label={t("legend")} className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
          {present.map(([key, total]) => (
            <li key={key ?? "mixed"} className="inline-flex items-center gap-2">
              <span aria-hidden="true" className="size-3 rounded-full" style={{ background: key ? (categoryOf.get(key)?.color ?? MIXED) : MIXED }} />
              {t("industryRow", { industry: industryName(key), count: number.format(total) })}
            </li>
          ))}
        </ul>
      )}

      {cities.length > 0 && (
        <CollapsibleSection title={t("showTable")}>
          {/* eslint-disable-next-line design-system/no-handrolled-ui -- DataTable lands in W4-1 */}
          <table className="w-full text-start text-sm">
            <thead>
              <tr className="text-muted">
                <th scope="col" className="py-1 text-start font-normal">{t("table.city")}</th>
                <th scope="col" className="py-1 text-start font-normal">{t("table.total")}</th>
                <th scope="col" className="py-1 text-start font-normal">{t("table.industries")}</th>
              </tr>
            </thead>
            <tbody>
              {cities.map((city) => (
                <tr key={city.code} className="border-t border-border">
                  <td dir="auto" className="py-1.5">{city.name}</td>
                  <td className="py-1.5">{number.format(city.total)}</td>
                  <td className="py-1.5 text-muted">{city.industries.map((i) => t("industryRow", { industry: industryName(i.key), count: number.format(i.total) })).join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CollapsibleSection>
      )}
    </div>
  );
}
