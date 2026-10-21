"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type { Map as MapLibreMap, Marker } from "maplibre-gl";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { currentTone, followTheme, styleUrl } from "./map-core";

type Props = {
  latitude: number | null;
  longitude: number | null;
  readOnly?: boolean;
};

/** A small map with the branch's pin. Dragging the pin corrects the point the address was
 * translated to; the form then sends the new point (`latitude`, `longitude`) with the rest. Until
 * it is moved, nothing is sent, so a changed address is looked up again instead. */
export function PinPicker({ latitude, longitude, readOnly = false }: Props) {
  const t = useTranslations("branchMap.pin");
  const container = useRef<HTMLDivElement>(null);
  const [moved, setMoved] = useState<{ lat: number; lng: number } | null>(null);
  const [failed, setFailed] = useState(false);
  const has = latitude !== null && longitude !== null;

  useEffect(() => {
    if (!has) return;
    let cancelled = false;
    let stopTheme = () => {};
    let map: MapLibreMap | null = null;
    let marker: Marker | null = null;
    (async () => {
      try {
        const maplibre = await import("maplibre-gl");
        if (cancelled || !container.current) return;
        map = new maplibre.Map({
          container: container.current,
          style: styleUrl(currentTone()),
          center: [longitude, latitude],
          zoom: 15,
          cooperativeGestures: true,
        });
        map.addControl(new maplibre.NavigationControl({ showCompass: false }), "bottom-right");
        stopTheme = followTheme(map);
        marker = new maplibre.Marker({ draggable: !readOnly }).setLngLat([longitude, latitude]).addTo(map);
        marker.on("dragend", () => {
          const at = marker?.getLngLat();
          if (at) setMoved({ lat: Number(at.lat.toFixed(6)), lng: Number(at.lng.toFixed(6)) });
        });
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      stopTheme();
      marker?.remove();
      map?.remove();
    };
  }, [has, latitude, longitude, readOnly]);

  if (!has) return <p className="text-sm text-muted">{t("none")}</p>;
  return (
    <div className="flex flex-col gap-2">
      <div className="relative h-56 overflow-hidden rounded-xl border border-border">
        <div ref={container} className="absolute inset-0" role="region" aria-label={t("label")} />
        {failed && <p className="absolute inset-0 flex items-center justify-center p-4 text-center text-sm text-muted">{t("failed")}</p>}
      </div>
      <p className="text-sm text-muted">{readOnly ? t("readOnly") : moved ? t("moved") : t("hint")}</p>
      {moved && (
        <>
          <input type="hidden" name="latitude" value={moved.lat} />
          <input type="hidden" name="longitude" value={moved.lng} />
        </>
      )}
    </div>
  );
}
