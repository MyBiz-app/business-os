"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type { Map as MapLibreMap, Marker } from "maplibre-gl";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { currentTone, followTheme, loadMaplibre, styleUrl } from "@/components/branch-map/map-core";

export type CoverageCity = { name: string; latitude: number; longitude: number; businesses: number };

const SMALL = 18;
const BIG = 52;

/** "MyBiz across the country": a dot per city sized by how many businesses are there. The map
 * starts only when it scrolls into view, so the home page does not pay for it up front. */
export function CoverageMap({ cities }: { cities: CoverageCity[] }) {
  const t = useTranslations("marketing.coverage");
  const locale = useLocale();
  const wrapper = useRef<HTMLDivElement>(null);
  const container = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [failed, setFailed] = useState(false);
  const [hovered, setHovered] = useState<CoverageCity | null>(null);

  useEffect(() => {
    const node = wrapper.current;
    if (!node || typeof IntersectionObserver === "undefined") return setVisible(true);
    const observer = new IntersectionObserver((entries) => entries.some((e) => e.isIntersecting) && setVisible(true), { rootMargin: "200px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    let map: MapLibreMap | null = null;
    let stopTheme = () => {};
    const markers: Marker[] = [];
    (async () => {
      try {
        const maplibre = await loadMaplibre();
        if (cancelled || !container.current) return;
        map = new maplibre.Map({
          container: container.current,
          style: styleUrl(currentTone()),
          center: [34.85, 31.5],
          zoom: 6,
          attributionControl: { compact: true },
          cooperativeGestures: true,
        });
        stopTheme = followTheme(map);
        const largest = Math.max(1, ...cities.map((c) => c.businesses));
        const bounds = new maplibre.LngLatBounds();
        for (const city of cities) {
          const dot = document.createElement("button");
          dot.type = "button";
          dot.className = "business-dot";
          dot.style.width = dot.style.height = `${(SMALL + Math.sqrt(city.businesses / largest) * (BIG - SMALL)).toFixed(0)}px`;
          dot.style.background = "var(--primary)";
          dot.setAttribute("aria-label", t("dot", { city: city.name, count: city.businesses }));
          dot.addEventListener("mouseenter", () => setHovered(city));
          dot.addEventListener("mouseleave", () => setHovered(null));
          dot.addEventListener("focus", () => setHovered(city));
          dot.addEventListener("blur", () => setHovered(null));
          markers.push(new maplibre.Marker({ element: dot }).setLngLat([city.longitude, city.latitude]).addTo(map));
          bounds.extend([city.longitude, city.latitude]);
        }
        if (cities.length > 1) map.fitBounds(bounds, { padding: 70, maxZoom: 9, duration: 0 });
        else map.jumpTo({ center: [cities[0].longitude, cities[0].latitude], zoom: 9 });
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      stopTheme();
      markers.forEach((marker) => marker.remove());
      map?.remove();
    };
  }, [visible, cities, t]);

  return (
    <div ref={wrapper} className="flex flex-col gap-4">
      <div className="relative isolate h-[26rem] overflow-hidden card sm:h-[32rem]">
        {/* MapLibre's own stylesheet makes the map element `position: relative`, so the sizing is on a wrapper. */}
        <div className="absolute inset-0">
          <div ref={container} className="size-full" role="region" aria-label={t("mapLabel")} />
        </div>
        {failed && <p className="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-muted">{t("failed")}</p>}
        {hovered && (
          <div role="status" className="pointer-events-none absolute end-3 top-3 z-10 flex flex-col gap-1 card p-3 text-sm">
            <span dir="auto" className="font-semibold">{hovered.name}</span>
            <span>{t("hover", { count: hovered.businesses })}</span>
          </div>
        )}
      </div>
      {/* The same facts as text, for screen readers and for anyone who skips the map. */}
      <ul className="sr-only" lang={locale}>
        {cities.map((city) => (
          <li key={city.name}>{t("dot", { city: city.name, count: city.businesses })}</li>
        ))}
      </ul>
      <p className="text-center text-sm text-muted">{t("privacy")}</p>
    </div>
  );
}
