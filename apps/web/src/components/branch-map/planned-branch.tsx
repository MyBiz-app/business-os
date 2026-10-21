"use client";

import type { GeoJSONSource, Map as MapLibreMap, Marker } from "maplibre-gl";
import { MapPin } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState, type RefObject } from "react";

import { Button } from "@/components/ui/button";

import { loadMaplibre, prefersReducedMotion } from "./map-core";
import { RADII_KM, circleRing, planBranch, type BranchSpot, type ClientCity, type LngLat } from "./planned-core";

type Props = {
  mapRef: RefObject<MapLibreMap | null>;
  branches: BranchSpot[];
  cities: ClientCity[];
  /** All the business's clients (also the ones with no city), for the "not counted" line. */
  total: number;
};

const FALLBACK = "royalblue";
const STEP_KM = 0.5;
const BIG_STEP_KM = 5;

/** A CSS color of the page, as a string the map library can read. */
const colorOf = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || FALLBACK;

/** Where the pin starts: the city with the most clients that has no branch, else the middle of
 * the country. */
function startingPin(cities: ClientCity[], branches: BranchSpot[]): LngLat {
  const hasBranch = new Set(branches.map((b) => b.cityCode));
  const top = cities.filter((c) => c.latitude !== null && c.longitude !== null && !hasBranch.has(c.code)).sort((a, b) => b.clients - a.clients)[0];
  if (top) return { latitude: top.latitude as number, longitude: top.longitude as number };
  return { latitude: 31.5, longitude: 34.85 };
}

/** The "planned branch" mode: a pin to drag, rings of 3, 5 and 10 km around it and, live, how many
 * clients live inside each, how far the nearest branch is and which cities send clients without a
 * branch. Cities come from the clients' saved city, never from an address. */
export function PlannedBranch({ mapRef, branches, cities, total }: Props) {
  const t = useTranslations("branchMap.planned");
  const locale = useLocale();
  const number = useMemo(() => new Intl.NumberFormat(locale), [locale]);
  const percent = useMemo(() => new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 0 }), [locale]);
  const km = useMemo(() => new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }), [locale]);
  const [pin, setPin] = useState<LngLat>(() => startingPin(cities, branches));
  const marker = useRef<Marker | null>(null);
  const pinRef = useRef(pin);
  const plan = useMemo(() => planBranch(pin, cities, branches), [pin, cities, branches]);

  useEffect(() => {
    pinRef.current = pin;
  }, [pin]);

  // The layers and the pin, for as long as the mode is on. A theme change reloads the style and
  // wipes the layers, so they are added again on every style load.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    let cancelled = false;
    const placed = cities.filter((c) => c.latitude !== null && c.longitude !== null);

    const rings = (at: LngLat) => ({
      type: "FeatureCollection" as const,
      features: [...RADII_KM].reverse().map((radius) => ({
        type: "Feature" as const,
        properties: { km: radius },
        geometry: { type: "Polygon" as const, coordinates: [circleRing(at, radius)] },
      })),
    });
    const dots = {
      type: "FeatureCollection" as const,
      features: placed.map((c) => ({
        type: "Feature" as const,
        properties: { clients: c.clients },
        geometry: { type: "Point" as const, coordinates: [c.longitude as number, c.latitude as number] },
      })),
    };

    function addLayers() {
      if (!map || map.getSource("planned-rings")) return;
      const primary = colorOf("--primary");
      map.addSource("planned-cities", { type: "geojson", data: dots });
      map.addSource("planned-rings", { type: "geojson", data: rings(pinRef.current) });
      map.addLayer({
        id: "planned-rings-fill",
        type: "fill",
        source: "planned-rings",
        paint: { "fill-color": primary, "fill-opacity": 0.07 },
      });
      map.addLayer({
        id: "planned-rings-line",
        type: "line",
        source: "planned-rings",
        paint: { "line-color": primary, "line-width": 1.5, "line-opacity": 0.75, "line-dasharray": [2, 2] },
      });
      map.addLayer({
        id: "planned-cities",
        type: "circle",
        source: "planned-cities",
        paint: {
          "circle-radius": ["min", 24, ["+", 4, ["*", 2.4, ["sqrt", ["get", "clients"]]]]],
          "circle-color": colorOf("--brand-to"),
          "circle-opacity": 0.55,
          "circle-stroke-color": colorOf("--surface"),
          "circle-stroke-width": 1.5,
        },
      });
    }

    const element = document.createElement("div");
    element.className = "planned-pin";
    element.tabIndex = 0;
    element.setAttribute("role", "button");
    element.setAttribute("aria-label", t("pinLabel"));
    element.setAttribute("aria-describedby", "planned-pin-help");
    // MapLibre positions the element itself, so the drawn pin is a child it does not touch.
    const shape = document.createElement("span");
    shape.className = "planned-pin-shape";
    element.append(shape);
    const move = (to: LngLat) => setPin({ latitude: Number(to.latitude.toFixed(5)), longitude: Number(to.longitude.toFixed(5)) });

    // Keys move the pin by 500 m, or by 5 km with Shift, so it works without a mouse too.
    element.addEventListener("keydown", (event) => {
      const arrows: Record<string, [number, number]> = { ArrowUp: [1, 0], ArrowDown: [-1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
      const step = arrows[event.key];
      if (!step) return;
      event.preventDefault();
      const size = (event.shiftKey ? BIG_STEP_KM : STEP_KM) / 111.32;
      const at = pinRef.current;
      move({ latitude: at.latitude + step[0] * size, longitude: at.longitude + (step[1] * size) / Math.cos((at.latitude * Math.PI) / 180) });
    });

    (async () => {
      const maplibre = await loadMaplibre();
      if (cancelled) return;
      const pinMarker = new maplibre.Marker({ element, draggable: true, anchor: "bottom" }).setLngLat([pinRef.current.longitude, pinRef.current.latitude]).addTo(map);
      pinMarker.on("drag", () => {
        const at = pinMarker.getLngLat();
        move({ latitude: at.lat, longitude: at.lng });
      });
      marker.current = pinMarker;
      if (map.isStyleLoaded()) addLayers();
      map.on("style.load", addLayers);
      // Show the pin and its widest ring.
      const bounds = new maplibre.LngLatBounds();
      for (const [lng, lat] of circleRing(pinRef.current, RADII_KM[RADII_KM.length - 1])) bounds.extend([lng, lat]);
      map.fitBounds(bounds, { padding: 60, duration: prefersReducedMotion() ? 0 : 700 });
    })();

    const onClick = (event: { lngLat: { lat: number; lng: number } }) => move({ latitude: event.lngLat.lat, longitude: event.lngLat.lng });
    map.on("click", onClick);
    const canvas = map.getCanvas();
    canvas.style.cursor = "crosshair";

    return () => {
      cancelled = true;
      map.off("click", onClick);
      map.off("style.load", addLayers);
      canvas.style.cursor = "";
      marker.current?.remove();
      marker.current = null;
      for (const id of ["planned-rings-fill", "planned-rings-line", "planned-cities"]) if (map.getLayer(id)) map.removeLayer(id);
      for (const id of ["planned-rings", "planned-cities"]) if (map.getSource(id)) map.removeSource(id);
    };
  }, [mapRef, cities, t]);

  // The pin and the rings follow the numbers.
  useEffect(() => {
    marker.current?.setLngLat([pin.longitude, pin.latitude]);
    const source = mapRef.current?.getSource("planned-rings") as GeoJSONSource | undefined;
    source?.setData({
      type: "FeatureCollection",
      features: [...RADII_KM].reverse().map((radius) => ({
        type: "Feature",
        properties: { km: radius },
        geometry: { type: "Polygon", coordinates: [circleRing(pin, radius)] },
      })),
    });
  }, [mapRef, pin]);

  const moveTo = (city: { latitude: number; longitude: number }) => {
    setPin({ latitude: city.latitude, longitude: city.longitude });
    const map = mapRef.current;
    if (!map) return;
    const to = { center: [city.longitude, city.latitude] as [number, number] };
    if (prefersReducedMotion()) map.jumpTo(to);
    else map.easeTo({ ...to, duration: 600 });
  };

  const noCity = Math.max(0, total - plan.placed - plan.unplaced);
  const empty = cities.length === 0;

  return (
    <aside
      aria-label={t("title")}
      className="absolute inset-x-0 bottom-0 z-20 flex max-h-[60%] flex-col gap-4 overflow-y-auto border-t border-border bg-surface p-5 shadow-lg sm:inset-y-0 sm:end-auto sm:start-0 sm:max-h-none sm:w-full sm:max-w-sm sm:border-e sm:border-t-0"
    >
      <div className="flex flex-col gap-1">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <MapPin aria-hidden="true" className="size-5 text-primary-ink" />
          {t("title")}
        </h2>
        <p id="planned-pin-help" className="text-sm text-muted">
          {t("help")}
        </p>
      </div>

      {empty ? (
        <p className="text-sm text-muted">{t("empty")}</p>
      ) : (
        <>
          <dl className="grid grid-cols-3 gap-2 text-sm" aria-label={t("rangesLabel")}>
            {plan.radii.map((r) => (
              <div key={r.km} className="flex flex-col gap-0.5 rounded-xl bg-primary/5 p-3">
                <dt className="text-xs text-muted">{t("within", { km: r.km })}</dt>
                <dd className="text-lg font-semibold">{number.format(r.clients)}</dd>
                <dd className="text-xs text-muted">{percent.format(r.share)}</dd>
              </div>
            ))}
          </dl>

          <p className="text-sm" role="status">
            {plan.nearest ? t.rich("nearest", { place: (chunks) => <bdi>{chunks}</bdi>, name: plan.nearest.name, km: km.format(plan.nearest.km) }) : t("noBranch")}
          </p>

          <section className="flex flex-col gap-2">
            <h3 className="text-xs text-muted">{t("withoutBranch")}</h3>
            {plan.withoutBranch.length === 0 ? (
              <p className="text-sm text-muted">{t("withoutBranchNone")}</p>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {plan.withoutBranch.map((city) => (
                  <li key={city.code} className="flex items-center justify-between gap-3 text-sm">
                    <div className="flex min-w-0 flex-col">
                      <span dir="auto" className="truncate">
                        {t("cityRow", { city: city.name, count: number.format(city.clients) })}
                      </span>
                      <span className="text-xs text-muted">
                        {city.nearestBranchKm === null ? t("fromPin", { km: km.format(city.fromPinKm) }) : t("fromPinAndBranch", { pin: km.format(city.fromPinKm), branch: km.format(city.nearestBranchKm) })}
                      </span>
                    </div>
                    <Button className="shrink-0 px-2.5 py-1 text-xs" onClick={() => moveTo(city)}>
                      {t("moveHere")}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <p className="text-xs text-muted">
            {t("basis", { count: number.format(plan.placed) })}
            {plan.unplaced + noCity > 0 && ` ${t("notCounted", { count: number.format(plan.unplaced + noCity) })}`}
          </p>
        </>
      )}
    </aside>
  );
}
