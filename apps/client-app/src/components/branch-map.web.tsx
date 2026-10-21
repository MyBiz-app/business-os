import type { Map as MapLibreMap, Marker } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { hasPoint } from "@business-os/app-kit/lib/distance";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";
import type { Location } from "@/lib/use-locations";

/** Free vector tiles from OpenFreeMap (OpenStreetMap data, no key). Only public branch points
 * are drawn, never a person's position. */
const STYLES = { light: "https://tiles.openfreemap.org/styles/positron", dark: "https://tiles.openfreemap.org/styles/dark" } as const;

type Maplibre = typeof import("maplibre-gl");

/** The branches on a map. MapLibre 6 cannot get its worker from the bundler, so the file is
 * copied next to the app by scripts/copy-maplibre-worker.mjs and handed over here. */
export function BranchMap({ locations, selectedId, onSelect }: { locations: Location[]; selectedId?: string; onSelect?: (id: string) => void }) {
  const t = useTranslations("client.homeCards");
  const { scheme, palette, reduceMotion } = useTheme();
  const host = useRef<HTMLDivElement>(null);
  const library = useRef<Maplibre | null>(null);
  const map = useRef<MapLibreMap | null>(null);
  const markers = useRef<Marker[]>([]);
  const [ready, setReady] = useState(false);
  const placed = useMemo(() => locations.filter(hasPoint), [locations]);
  const hasPins = placed.length > 0;

  useEffect(() => {
    if (!hasPins) return;
    let gone = false;
    void import("maplibre-gl").then((maplibre) => {
      if (gone || !host.current) return;
      maplibre.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
      library.current = maplibre;
      map.current = new maplibre.Map({ container: host.current, style: STYLES[scheme], center: [34.85, 31.8], zoom: 6, attributionControl: { compact: true } });
      setReady(true);
    });
    return () => {
      gone = true;
      setReady(false);
      map.current?.remove();
      map.current = null;
    };
    // The map is built once per mount; the effects below keep its style, pins and view in step.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasPins]);

  useEffect(() => {
    if (ready) map.current?.setStyle(STYLES[scheme]);
  }, [ready, scheme]);

  useEffect(() => {
    const target = map.current;
    const maplibre = library.current;
    if (!ready || !target || !maplibre) return;
    markers.current.forEach((marker) => marker.remove());
    markers.current = placed.map((location) => {
      const size = location.id === selectedId ? "22px" : "16px";
      const pin = document.createElement("button");
      pin.type = "button";
      pin.setAttribute("aria-label", location.name);
      Object.assign(pin.style, { width: size, height: size, borderRadius: "50%", border: "3px solid #fff", background: palette.primary, boxShadow: "0 1px 4px rgba(0,0,0,.35)", cursor: "pointer", padding: "0" });
      pin.addEventListener("click", () => onSelect?.(location.id));
      return new maplibre.Marker({ element: pin }).setLngLat([location.longitude, location.latitude]).addTo(target);
    });
    const chosen = placed.find((l) => l.id === selectedId);
    const duration = reduceMotion ? 0 : 600;
    if (chosen) target.easeTo({ center: [chosen.longitude, chosen.latitude], zoom: 13, duration });
    else if (placed.length === 1) target.jumpTo({ center: [placed[0].longitude, placed[0].latitude], zoom: 13 });
    else target.fitBounds(placed.reduce((box, l) => box.extend([l.longitude, l.latitude]), new maplibre.LngLatBounds()), { padding: 40, duration, maxZoom: 13 });
  }, [ready, placed, selectedId, palette.primary, onSelect, reduceMotion]);

  if (!hasPins) return null;
  return (
    <View accessibilityLabel={t("mapLabel")} style={{ height: 220, borderRadius: 16, overflow: "hidden", backgroundColor: palette.border }}>
      <div ref={host} style={{ width: "100%", height: "100%" }} />
    </View>
  );
}
