"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type { GeoJSONSource, Map as MapLibreMap } from "maplibre-gl";
import { X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button, IconButton } from "@/components/ui/button";
import { StatTile } from "@/components/ui/stat-tile";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { DataTable } from "@/components/ui/data-table";

import { RADII_KM, circleRing, type BranchSpot } from "../branch-map/planned-core";
import { currentTone, followTheme, loadMaplibre, prefersReducedMotion, styleUrl } from "../branch-map/map-core";
import { cards, isPlaced, type Area } from "./insights-core";

type Layer = "branches" | "clients" | "leads" | "reach";
const LAYERS: Layer[] = ["branches", "clients", "leads", "reach"];

type Props = {
  areas: Area[];
  branches: BranchSpot[];
  totals: { clients: number; clientsWithoutCity: number; leads: number; leadsWithoutCity: number };
  /** Whether the person may open client cards: only then does a city link to its clients. */
  canOpenClients: boolean;
};

const FALLBACK = "royalblue";
const TABLE_ROWS = 100;
const colorOf = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || FALLBACK;
const collection = (features: object[]) => ({ type: "FeatureCollection" as const, features });

/** The business's insights map: a circle per city sized by its clients, a ring per city with leads,
 * the branches, and the 3 / 5 / 10 km reach around them. Counts only: no name or house number is
 * ever drawn, and nothing is hidden for being small (this is the business's own data). */
export function InsightsMap({ areas, branches, totals, canOpenClients }: Props) {
  const t = useTranslations("insightsMap");
  const locale = useLocale();
  const number = useMemo(() => new Intl.NumberFormat(locale), [locale]);
  const percent = (share: number) => `${number.format(Math.round(share * 100))}%`;
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [on, setOn] = useState<Record<Layer, boolean>>({ branches: true, clients: true, leads: true, reach: false });
  const [focus, setFocus] = useState<string>("all");
  const [picked, setPicked] = useState<number | null>(null);

  const numbers = useMemo(() => cards(areas, branches), [areas, branches]);
  const placed = useMemo(() => areas.filter(isPlaced), [areas]);
  const pickedArea = areas.find((a) => a.code === picked) ?? null;
  const ringBranches = focus === "all" ? branches : branches.filter((b) => b.id === focus);

  // Everything the map draws, rebuilt on every style load (a theme change wipes the layers).
  const data = useMemo(
    () => ({
      cities: collection(
        placed.map((a) => ({
          type: "Feature",
          properties: { code: a.code, clients: a.clients, leads: a.leads },
          geometry: { type: "Point", coordinates: [a.longitude, a.latitude] },
        })),
      ),
      branches: collection(branches.map((b) => ({ type: "Feature", properties: { id: b.id }, geometry: { type: "Point", coordinates: [b.longitude, b.latitude] } }))),
      rings: collection(
        ringBranches.flatMap((b) =>
          [...RADII_KM].reverse().map((km) => ({ type: "Feature", properties: { km }, geometry: { type: "Polygon", coordinates: [circleRing(b, km)] } })),
        ),
      ),
    }),
    [placed, branches, ringBranches],
  );
  const dataRef = useRef(data);
  const onRef = useRef(on);
  useEffect(() => {
    dataRef.current = data;
    onRef.current = on;
  });

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

        const visibility = (layer: Layer) => (onRef.current[layer] ? "visible" : "none");
        const addLayers = () => {
          if (map.getSource("insights-cities")) return;
          const primary = colorOf("--primary");
          const surface = colorOf("--surface");
          map.addSource("insights-cities", { type: "geojson", data: dataRef.current.cities });
          map.addSource("insights-branches", { type: "geojson", data: dataRef.current.branches });
          map.addSource("insights-rings", { type: "geojson", data: dataRef.current.rings });
          map.addLayer({ id: "insights-rings-fill", type: "fill", source: "insights-rings", layout: { visibility: visibility("reach") }, paint: { "fill-color": primary, "fill-opacity": 0.06 } });
          map.addLayer({
            id: "insights-rings-line",
            type: "line",
            source: "insights-rings",
            layout: { visibility: visibility("reach") },
            paint: { "line-color": primary, "line-width": 1.5, "line-opacity": 0.7, "line-dasharray": [2, 2] },
          });
          map.addLayer({
            id: "insights-clients",
            type: "circle",
            source: "insights-cities",
            filter: [">", ["get", "clients"], 0],
            layout: { visibility: visibility("clients") },
            paint: {
              "circle-radius": ["min", 28, ["+", 5, ["*", 2.6, ["sqrt", ["get", "clients"]]]]],
              "circle-color": colorOf("--brand-to"),
              "circle-opacity": 0.55,
              "circle-stroke-color": surface,
              "circle-stroke-width": 1.5,
            },
          });
          map.addLayer({
            id: "insights-leads",
            type: "circle",
            source: "insights-cities",
            filter: [">", ["get", "leads"], 0],
            layout: { visibility: visibility("leads") },
            paint: {
              "circle-radius": ["min", 30, ["+", 8, ["*", 2.6, ["sqrt", ["get", "leads"]]]]],
              "circle-color": "rgba(0,0,0,0)",
              "circle-stroke-color": colorOf("--warning"),
              "circle-stroke-width": 2.5,
            },
          });
          map.addLayer({
            id: "insights-branches",
            type: "circle",
            source: "insights-branches",
            layout: { visibility: visibility("branches") },
            paint: { "circle-radius": 7, "circle-color": primary, "circle-stroke-color": surface, "circle-stroke-width": 2.5 },
          });
        };
        map.on("style.load", addLayers);
        map.on("click", (event) => {
          const hit = map.queryRenderedFeatures(event.point, { layers: ["insights-clients", "insights-leads"].filter((id) => map.getLayer(id)) })[0];
          setPicked(hit ? Number(hit.properties?.code) : null);
        });
        for (const id of ["insights-clients", "insights-leads"]) {
          map.on("mouseenter", id, () => (map.getCanvas().style.cursor = "pointer"));
          map.on("mouseleave", id, () => (map.getCanvas().style.cursor = ""));
        }
        if (map.isStyleLoaded()) addLayers();

        const points = [...placed.map((a): [number, number] => [a.longitude, a.latitude]), ...branches.map((b): [number, number] => [b.longitude, b.latitude])];
        if (points.length > 1) {
          const bounds = new maplibre.LngLatBounds();
          for (const point of points) bounds.extend(point);
          map.fitBounds(bounds, { padding: 70, maxZoom: 10, duration: 0 });
        } else if (points.length === 1) map.jumpTo({ center: points[0], zoom: 10 });
        setReady(true);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      stopTheme();
      mapRef.current?.remove();
      mapRef.current = null;
    };
    // The map is created once; its data and layers follow the effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // New numbers (another period) or another branch in focus.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    (map.getSource("insights-cities") as GeoJSONSource | undefined)?.setData(data.cities);
    (map.getSource("insights-branches") as GeoJSONSource | undefined)?.setData(data.branches);
    (map.getSource("insights-rings") as GeoJSONSource | undefined)?.setData(data.rings);
  }, [ready, data]);

  // The layer switches.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const ids: Record<Layer, string[]> = {
      branches: ["insights-branches"],
      clients: ["insights-clients"],
      leads: ["insights-leads"],
      reach: ["insights-rings-fill", "insights-rings-line"],
    };
    for (const layer of LAYERS) for (const id of ids[layer]) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on[layer] ? "visible" : "none");
  }, [ready, on]);

  function flyTo(area: Area) {
    setPicked(area.code);
    if (isPlaced(area)) mapRef.current?.flyTo({ center: [area.longitude, area.latitude], zoom: 10, duration: prefersReducedMotion() ? 0 : 700 });
  }

  const cityButton = (code: number, name: string, detail: string) => {
    const area = areas.find((a) => a.code === code);
    return (
      <li key={code}>
        <Button variant="plain" onClick={() => area && flyTo(area)} className="flex w-full items-baseline justify-between gap-3 rounded-md px-2 py-1.5 text-start text-sm hover:bg-subtle">
          <span dir="auto" className="font-medium">{name}</span>
          <span className="text-muted tabular-nums">{detail}</span>
        </Button>
      </li>
    );
  };

  const reachLabel = (km: number) => t("reach.ring", { km });

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label={t("cards.clients")} value={number.format(totals.clients)} hint={totals.clientsWithoutCity > 0 ? t("cards.withoutCity", { count: number.format(totals.clientsWithoutCity) }) : undefined} />
        <StatTile label={t("cards.leads")} value={number.format(totals.leads)} hint={totals.leadsWithoutCity > 0 ? t("cards.withoutCity", { count: number.format(totals.leadsWithoutCity) }) : undefined} />
        <StatTile
          label={t("cards.within", { km: numbers.within?.km ?? RADII_KM[2] })}
          value={numbers.within ? percent(numbers.within.share) : "-"}
          hint={numbers.within ? t("cards.withinHint", { count: numbers.within.clients }) : t("cards.noBranch")}
        />
        <StatTile label={t("cards.whiteSpots")} value={number.format(numbers.whiteSpots.length)} hint={t("cards.whiteSpotsHint", { km: RADII_KM[2] })} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex flex-col gap-3">
          <fieldset className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <legend className="sr-only">{t("layers.label")}</legend>
            {LAYERS.map((layer) => (
              <label key={layer} className="inline-flex items-center gap-2 text-sm">
                <input type="checkbox" className="size-4 accent-[var(--primary)]" checked={on[layer]} onChange={(e) => setOn({ ...on, [layer]: e.target.checked })} />
                {t(`layers.${layer}`)}
              </label>
            ))}
            {on.reach && branches.length > 1 && (
              <label className="inline-flex items-center gap-2 text-sm">
                <span className="text-muted">{t("reach.branch")}</span>
                <select className="rounded-md border border-border bg-surface px-2 py-1" value={focus} onChange={(e) => setFocus(e.target.value)}>
                  <option value="all">{t("reach.all")}</option>
                  {branches.map((b) => (
                    <option key={b.id} value={b.id}>{b.name}</option>
                  ))}
                </select>
              </label>
            )}
          </fieldset>

          <div className="relative isolate h-[60vh] min-h-[24rem] overflow-hidden card">
            {/* MapLibre's stylesheet makes the map element `position: relative`, so the sizing is on a wrapper. */}
            <div className="absolute inset-0">
              <div ref={container} className="size-full" role="region" aria-label={t("mapLabel")} />
            </div>
            {failed && <p className="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-muted">{t("failed")}</p>}
            {ready && areas.length === 0 && branches.length === 0 && (
              <p role="status" className="pointer-events-none absolute inset-x-6 top-6 z-10 mx-auto max-w-md card p-4 text-center text-sm">{t("empty")}</p>
            )}
            {pickedArea && (
              <div role="status" className="absolute end-3 top-3 z-10 flex w-64 flex-col gap-1 card p-3 text-sm">
                <div className="flex items-start justify-between gap-2">
                  <span dir="auto" className="font-semibold">{pickedArea.name}</span>
                  <IconButton label={t("panel.close")} onClick={() => setPicked(null)}>
                    <X aria-hidden="true" className="size-4" />
                  </IconButton>
                </div>
                <span>{t("panel.clients", { count: pickedArea.clients, fresh: number.format(pickedArea.newClients) })}</span>
                <span>{t("panel.leads", { count: pickedArea.leads, won: number.format(pickedArea.leadsWon) })}</span>
                {canOpenClients && pickedArea.clients > 0 && (
                  <Link href={`/clients?city=${pickedArea.code}`} className="mt-1 text-primary-ink underline underline-offset-4 hover:no-underline">
                    {t("panel.open")}
                  </Link>
                )}
              </div>
            )}
          </div>
          <ul aria-label={t("legend.label")} className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
            <li className="inline-flex items-center gap-2"><span aria-hidden="true" className="size-3 rounded-full bg-[var(--brand-to)] opacity-60" />{t("legend.clients")}</li>
            <li className="inline-flex items-center gap-2"><span aria-hidden="true" className="size-3 rounded-full border-2 border-[var(--warning)]" />{t("legend.leads")}</li>
            <li className="inline-flex items-center gap-2"><span aria-hidden="true" className="size-3 rounded-full bg-[var(--primary)]" />{t("legend.branches")}</li>
            {on.reach && RADII_KM.map((km) => <li key={km} className="text-muted">{reachLabel(km)}</li>)}
          </ul>
        </div>

        <aside className="flex flex-col gap-5" aria-label={t("cards.label")}>
          <section className="flex flex-col gap-1">
            <h2 className="text-sm font-semibold">{t("top.title")}</h2>
            {numbers.topCities.length === 0 ? <p className="text-sm text-muted">{t("top.empty")}</p> : <ul>{numbers.topCities.map((c) => cityButton(c.code, c.name, t("top.row", { count: number.format(c.clients), share: percent(c.share) })))}</ul>}
          </section>
          <section className="flex flex-col gap-1">
            <h2 className="text-sm font-semibold">{t("white.title")}</h2>
            <p className="text-xs text-muted">{t("white.hint", { km: RADII_KM[2] })}</p>
            {numbers.whiteSpots.length === 0 ? <p className="text-sm text-muted">{t("white.empty")}</p> : <ul>{numbers.whiteSpots.map((s) => cityButton(s.code, s.name, t("white.row", { leads: s.leads })))}</ul>}
          </section>
          <section className="flex flex-col gap-1">
            <h2 className="text-sm font-semibold">{t("conversion.title")}</h2>
            {numbers.conversion.length === 0 ? <p className="text-sm text-muted">{t("conversion.empty")}</p> : <ul>{numbers.conversion.map((c) => cityButton(c.code, c.name, t("conversion.row", { won: number.format(c.won), leads: number.format(c.leads), rate: percent(c.rate) })))}</ul>}
          </section>
        </aside>
      </div>

      {areas.length > 0 && (
        <CollapsibleSection title={t("table.show")}>
          <DataTable<Area>
            bare
            density="compact"
            label={t("table.show")}
            rows={areas.slice(0, TABLE_ROWS)}
            rowKey={(a) => a.code}
            columns={[
              { key: "city", header: t("table.city"), rowHeader: true, cell: (a) => <bdi>{a.name}</bdi> },
              { key: "clients", header: t("table.clients"), align: "end", cell: (a) => number.format(a.clients) },
              { key: "newClients", header: t("table.newClients"), align: "end", hideBelow: "sm", cell: (a) => number.format(a.newClients) },
              { key: "leads", header: t("table.leads"), align: "end", cell: (a) => number.format(a.leads) },
              { key: "won", header: t("table.won"), align: "end", hideBelow: "sm", cell: (a) => number.format(a.leadsWon) },
            ]}
          />
        </CollapsibleSection>
      )}
    </div>
  );
}
