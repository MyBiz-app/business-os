"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type { Map as MapLibreMap, Marker } from "maplibre-gl";
import { CalendarDays, FileBarChart, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { SegmentedControl } from "@/components/segmented-control";
import { formatMoney } from "@/lib/money";

import { currentTone, followTheme, loadMaplibre, prefersReducedMotion, share, styleUrl } from "./map-core";
import { PlannedBranch } from "./planned-branch";
import type { ClientCity } from "./planned-core";

export type MapBranch = {
  id: string;
  name: string;
  city: string | null;
  /** The city's code in the official list (a branch counts as "in" that city). */
  cityCode: number | null;
  latitude: number;
  longitude: number;
  revenue: number | null;
  clients: number | null;
  occupancy: number | null;
  bookings: number | null;
  /** Revenue per day for the last 30 days, oldest first. */
  series: number[];
  /** A session is running there right now. */
  live: boolean;
  /** The cities clients of the last 30 days come from, most first (a point when it was found). */
  origins: { city: string; clients: number; latitude: number | null; longitude: number | null }[];
  /** The branch's share of the latest payroll month's pay (minor units); null without payroll access. */
  staffCost: number | null;
  /** The payroll month (YYYY-MM-DD) the cost is from. */
  staffCostMonth: string | null;
  /** Team members assigned to the branch or based there. */
  staffCount: number;
};

type ColorBy = "revenue" | "clients" | "occupancy";
type Mode = "branches" | "planned";

const SMALL = 14;
const BIG = 38;

type Props = {
  branches: MapBranch[];
  currency: string;
  /** "card" is the small dashboard version: no side panel, a click opens the full map. */
  variant?: "full" | "card";
  initialBranch?: string | null;
  /** Shows where clients come from from the start, also in the card (a business with one branch). */
  originsOn?: boolean;
  /** Server action: opens the branch's report or schedule (form field `branch_id`, `to`). */
  openBranch?: (formData: FormData) => Promise<void>;
  /** Where the clients live, by city. Without it there is no "planned branch" mode. */
  clientCities?: { cities: ClientCity[]; total: number } | null;
};

function Sparkline({ values }: { values: number[] }) {
  const max = Math.max(1, ...values);
  const step = values.length > 1 ? 100 / (values.length - 1) : 0;
  const points = values.map((v, i) => `${(i * step).toFixed(1)},${(30 - (v / max) * 28).toFixed(1)}`).join(" ");
  return (
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" role="img" className="h-16 w-full text-primary" aria-hidden="true">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** The branches on a map: a dot per branch sized by the chosen number, a card on hover and, in
 * the full version, a side panel that the map flies to when a branch is chosen. */
export function BranchMap({ branches, currency, variant = "full", initialBranch = null, originsOn = false, openBranch, clientCities = null }: Props) {
  const t = useTranslations("branchMap");
  const locale = useLocale();
  const full = variant === "full";
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markers = useRef<Map<string, { marker: Marker; dot: HTMLElement }>>(new Map());
  const [ready, setReady] = useState(false);
  const [colorBy, setColorBy] = useState<ColorBy>("revenue");
  const [selected, setSelected] = useState<string | null>(initialBranch);
  const [hovered, setHovered] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [showOrigins, setShowOrigins] = useState(originsOn);
  const [mode, setMode] = useState<Mode>("branches");
  const planning = full && mode === "planned" && clientCities !== null;
  const originMarkers = useRef<Marker[]>([]);

  const number = useMemo(() => new Intl.NumberFormat(locale), [locale]);
  const metric = (branch: MapBranch, key: ColorBy) => (key === "revenue" ? branch.revenue : key === "clients" ? branch.clients : branch.occupancy);
  const money = (value: number | null) => (value === null ? "-" : formatMoney(Math.round(value), currency, locale));
  const percent = (value: number | null) => (value === null ? "-" : `${number.format(Math.round(value))}%`);
  const count = (value: number | null) => (value === null ? "-" : number.format(value));

  const branchesRef = useRef(branches);
  useEffect(() => {
    branchesRef.current = branches;
  }, [branches]);

  // The map itself, created once the library has loaded (it is only needed on this page).
  useEffect(() => {
    let cancelled = false;
    let stopTheme = () => {};
    const nodes = markers.current;
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
          cooperativeGestures: !full,
        });
        mapRef.current = map;
        map.addControl(new maplibre.NavigationControl({ showCompass: false }), "bottom-right");
        stopTheme = followTheme(map);
        const points = branchesRef.current;
        for (const branch of points) {
          const dot = document.createElement("button");
          dot.type = "button";
          dot.setAttribute("aria-label", branch.name);
          dot.className = "branch-dot";
          dot.addEventListener("click", () => setSelected(branch.id));
          dot.addEventListener("mouseenter", () => setHovered(branch.id));
          dot.addEventListener("mouseleave", () => setHovered(null));
          dot.addEventListener("focus", () => setHovered(branch.id));
          dot.addEventListener("blur", () => setHovered(null));
          const marker = new maplibre.Marker({ element: dot }).setLngLat([branch.longitude, branch.latitude]).addTo(map);
          nodes.set(branch.id, { marker, dot });
        }
        if (points.length === 1) map.jumpTo({ center: [points[0].longitude, points[0].latitude], zoom: 11 });
        else if (points.length > 1) {
          const bounds = new maplibre.LngLatBounds();
          for (const p of points) bounds.extend([p.longitude, p.latitude]);
          map.fitBounds(bounds, { padding: 70, maxZoom: 11, duration: 0 });
        }
        setReady(true);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      stopTheme();
      for (const { marker } of nodes.values()) marker.remove();
      nodes.clear();
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [full]);

  // Size and color follow the chosen number; the dots change smoothly (CSS transitions).
  useEffect(() => {
    if (!ready) return;
    const values = branches.map((b) => metric(b, colorBy));
    for (const branch of branches) {
      const node = markers.current.get(branch.id);
      if (!node) continue;
      const weight = share(metric(branch, colorBy), values);
      const size = SMALL + weight * (BIG - SMALL);
      node.dot.style.setProperty("--dot-size", `${size.toFixed(0)}px`);
      node.dot.style.setProperty("--dot-weight", `${Math.round(30 + weight * 70)}%`);
      node.dot.dataset.live = branch.live ? "true" : "false";
      node.dot.dataset.selected = selected === branch.id ? "true" : "false";
    }
  }, [ready, branches, colorBy, selected]);

  // Choosing a branch: the map flies to its street while the panel opens.
  useEffect(() => {
    const map = mapRef.current;
    const branch = branches.find((b) => b.id === selected);
    if (!ready || !map || !branch || planning) return;
    const to = { center: [branch.longitude, branch.latitude] as [number, number], zoom: 15 };
    if (prefersReducedMotion()) map.jumpTo(to);
    else map.flyTo({ ...to, speed: 0.8, curve: 1.6, essential: false });
  }, [ready, selected, branches, planning]);

  // "Where clients come from": a dot per city, for the chosen branch (or all of them when none is).
  useEffect(() => {
    for (const marker of originMarkers.current) marker.remove();
    originMarkers.current = [];
    const map = mapRef.current;
    if (!ready || !map || !showOrigins || !(full || originsOn) || planning) return;
    let cancelled = false;
    (async () => {
      const maplibre = await loadMaplibre();
      if (cancelled) return;
      const chosen = selected ? branches.filter((b) => b.id === selected) : branches;
      const byCity = new Map<string, { city: string; clients: number; latitude: number; longitude: number }>();
      for (const branch of chosen) {
        for (const o of branch.origins) {
          if (o.latitude === null || o.longitude === null) continue;
          const key = `${o.latitude},${o.longitude}`;
          const known = byCity.get(key);
          byCity.set(key, { city: o.city, latitude: o.latitude, longitude: o.longitude, clients: (known?.clients ?? 0) + o.clients });
        }
      }
      for (const o of byCity.values()) {
        const dot = document.createElement("div");
        dot.className = "origin-dot";
        const size = 10 + Math.min(18, Math.sqrt(o.clients) * 4);
        dot.style.width = dot.style.height = `${size.toFixed(0)}px`;
        dot.title = t("originPoint", { city: o.city, count: o.clients });
        originMarkers.current.push(new maplibre.Marker({ element: dot }).setLngLat([o.longitude, o.latitude]).addTo(map));
      }
      // The card shows the branch and the cities its clients come from in one view.
      if (!full && byCity.size > 0) {
        const bounds = new maplibre.LngLatBounds();
        for (const b of chosen) bounds.extend([b.longitude, b.latitude]);
        for (const o of byCity.values()) bounds.extend([o.longitude, o.latitude]);
        map.fitBounds(bounds, { padding: 50, maxZoom: 11, duration: 0 });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [ready, showOrigins, selected, branches, full, originsOn, planning, t]);

  const open = planning ? null : (branches.find((b) => b.id === selected) ?? null);
  const peek = branches.find((b) => b.id === hovered) ?? null;
  const modes: { value: Mode; label: string }[] = [
    { value: "branches", label: t("mode.branches") },
    { value: "planned", label: t("mode.planned") },
  ];
  const toggles: { value: ColorBy; label: string }[] = [
    { value: "revenue", label: t("colorBy.revenue") },
    { value: "clients", label: t("colorBy.clients") },
    { value: "occupancy", label: t("colorBy.occupancy") },
  ];

  return (
    <div className={`relative isolate overflow-hidden rounded-2xl border border-border bg-surface ${full ? "h-[70vh] min-h-[28rem]" : "h-64"}`}>
      {/* MapLibre's own stylesheet makes the map element `position: relative`, so the sizing is on a wrapper. */}
        <div className="absolute inset-0">
          <div ref={container} className="size-full" role="region" aria-label={t("mapLabel")} />
        </div>
      {failed && <p className="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-muted">{t("failed")}</p>}
      {full && (
        <div className="absolute start-3 top-3 z-10 max-w-[calc(100%-1.5rem)]">
          <div className="flex flex-col items-start gap-2">
            {clientCities && <SegmentedControl label={t("mode.label")} value={mode} options={modes} onChange={setMode} />}
            {!planning && (
              <>
                <SegmentedControl label={t("colorByLabel")} value={colorBy} options={toggles} onChange={setColorBy} />
                <label className="card inline-flex items-center gap-2 px-3 py-1.5 text-sm">
                  <input type="checkbox" checked={showOrigins} onChange={(e) => setShowOrigins(e.target.checked)} />
                  {t("originsLayer")}
                </label>
              </>
            )}
          </div>
        </div>
      )}
      {peek && !open && (
        <div role="status" className="pointer-events-none absolute end-3 top-3 z-10 flex w-56 flex-col gap-1 card p-3 text-sm">
          <span dir="auto" className="font-semibold">{peek.name}</span>
          {peek.city && <span dir="auto" className="text-muted">{peek.city}</span>}
          <span>{t("hover.clients", { value: count(peek.clients) })}</span>
          <span>{t("hover.revenue", { value: money(peek.revenue) })}</span>
          <span>{t("hover.occupancy", { value: percent(peek.occupancy) })}</span>
        </div>
      )}
      {!full && (
        <Link
          href={`/locations/map${selected ? `?branch=${selected}` : ""}`}
          className="btn-secondary absolute end-3 bottom-3 z-10 px-3 py-1.5 text-sm"
        >
          {t("openFull")}
        </Link>
      )}
      {planning && ready && clientCities && (
        <PlannedBranch
          mapRef={mapRef}
          branches={branches.map((b) => ({ id: b.id, name: b.name, cityCode: b.cityCode, latitude: b.latitude, longitude: b.longitude }))}
          cities={clientCities.cities}
          total={clientCities.total}
        />
      )}
      {full && open && (
        <aside aria-label={open.name} className="absolute inset-y-0 start-0 z-20 flex w-full max-w-sm flex-col gap-4 overflow-y-auto border-e border-border bg-surface p-5 shadow-lg">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 flex-col">
              <h2 dir="auto" className="truncate text-lg font-semibold">{open.name}</h2>
              {open.city && <span dir="auto" className="text-sm text-muted">{open.city}</span>}
            </div>
            <button type="button" className="btn-plain shrink-0 p-1.5" aria-label={t("close")} onClick={() => setSelected(null)}>
              <X aria-hidden="true" className="size-5" />
            </button>
          </div>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <Stat label={t("panel.revenue")} value={money(open.revenue)} />
            <Stat label={t("panel.clients")} value={count(open.clients)} />
            <Stat label={t("panel.bookings")} value={count(open.bookings)} />
            <Stat label={t("panel.occupancy")} value={percent(open.occupancy)} />
            <Stat label={t("panel.staffCount")} value={count(open.staffCount)} />
          </dl>
          {open.staffCost !== null && open.staffCostMonth && (
            <dl className="grid grid-cols-1 gap-3 text-sm">
              <Stat
                label={t("panel.staffCost", { month: new Intl.DateTimeFormat(locale, { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(open.staffCostMonth)) })}
                value={money(open.staffCost)}
                hint={t("panel.staffCostHint")}
              />
            </dl>
          )}
          <section className="flex flex-col gap-1">
            <h3 className="text-xs text-muted">{t("panel.origins")}</h3>
            {open.origins.length === 0 ? (
              <p className="text-sm text-muted">{t("panel.originsEmpty")}</p>
            ) : (
              <ul className="flex flex-col gap-0.5 text-sm">
                {open.origins.map((o) => (
                  <li key={o.city} dir="auto">
                    {t("panel.originRow", { city: o.city, count: number.format(o.clients) })}
                  </li>
                ))}
              </ul>
            )}
          </section>
          <figure className="flex flex-col gap-1">
            <figcaption className="text-xs text-muted">{t("panel.trend")}</figcaption>
            <Sparkline values={open.series} />
          </figure>
          {openBranch && (
            <div className="mt-auto flex flex-col gap-2">
              {(
                [
                  ["reports", t("panel.report"), FileBarChart],
                  ["schedule", t("panel.schedule"), CalendarDays],
                ] as const
              ).map(([to, label, Icon]) => (
                <form key={to} action={openBranch}>
                  <input type="hidden" name="branch_id" value={open.id} />
                  <input type="hidden" name="to" value={to} />
                  <button type="submit" className="btn-secondary inline-flex w-full items-center justify-center gap-2 px-4 py-2.5">
                    <Icon aria-hidden="true" className="size-4" />
                    {label}
                  </button>
                </form>
              ))}
            </div>
          )}
        </aside>
      )}
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-xl bg-primary/5 p-3">
      <dt className="text-xs text-muted">{label}</dt>
      <dd dir="auto" className="text-base font-semibold">{value}</dd>
      {hint && <dd className="text-xs text-muted">{hint}</dd>}
    </div>
  );
}
