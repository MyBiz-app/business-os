"use client";

import { Minus, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { clampView, type CropView, croppedName, cropSquare, MAX_ZOOM, MIN_ZOOM, zoomTo } from "@/lib/image-crop";

const BOX = 288; // the crop box, in CSS pixels
const OUTPUT = 512; // the saved picture is OUTPUT x OUTPUT pixels
const MAX_BYTES = 500 * 1024; // the API refuses pictures over 512 KB
const KEY_STEP = 12;

type Loaded = { url: string; width: number; height: number };

function toBlob(canvas: HTMLCanvasElement, type: string, quality: number) {
  return new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, type, quality));
}

/** Draws the chosen square into an OUTPUT-sized picture, lowering the quality or size until it
 * fits what the API accepts. WebP keeps a logo's transparent corners. */
async function render(image: HTMLImageElement, view: CropView, name: string): Promise<File | null> {
  const { sx, sy, side } = cropSquare(view, image.naturalWidth, image.naturalHeight, BOX);
  for (const size of [OUTPUT, 384, 256]) {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = size;
    canvas.getContext("2d")?.drawImage(image, sx, sy, side, side, 0, 0, size, size);
    for (const quality of [0.92, 0.8, 0.6]) {
      const blob = await toBlob(canvas, "image/webp", quality);
      if (blob && blob.size <= MAX_BYTES) return new File([blob], croppedName(name, blob.type), { type: blob.type });
    }
  }
  return null;
}

/** A square window over the chosen picture, with a circle showing how it will look: drag to
 * move, slide or scroll to zoom, arrow keys and +/- from the keyboard. */
export function ImageCropDialog({ file, onDone, onCancel }: { file: File; onDone: (cropped: File) => void; onCancel: () => void }) {
  const t = useTranslations("imageCrop");
  const dialog = useRef<HTMLDialogElement>(null);
  const image = useRef<HTMLImageElement>(null);
  const drag = useRef<{ pointer: number; x: number; y: number; start: CropView } | null>(null);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [view, setView] = useState<CropView>({ zoom: 1, x: 0, y: 0 });
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    dialog.current?.showModal();
    const url = URL.createObjectURL(file);
    const probe = new Image();
    probe.onload = () => setLoaded({ url, width: probe.naturalWidth, height: probe.naturalHeight });
    probe.onerror = () => setFailed(true);
    probe.src = url;
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const move = useCallback(
    (next: CropView) => loaded && setView(clampView(next, loaded.width, loaded.height, BOX)),
    [loaded],
  );
  const zoom = useCallback(
    (value: number) => loaded && setView((current) => zoomTo(current, Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value)), loaded.width, loaded.height, BOX)),
    [loaded],
  );

  const scale = loaded ? (BOX / Math.min(loaded.width, loaded.height)) * view.zoom : 1;

  async function confirm() {
    if (!image.current || busy) return;
    setBusy(true);
    const cropped = await render(image.current, view, file.name);
    setBusy(false);
    if (cropped) onDone(cropped);
    else setFailed(true);
  }

  return (
    <dialog
      ref={dialog}
      aria-labelledby="crop-title"
      onCancel={(event) => {
        event.preventDefault();
        onCancel();
      }}
      className="m-auto w-[min(92vw,26rem)] rounded-3xl border border-border bg-surface p-0 text-foreground shadow-2xl backdrop:bg-black/60"
    >
      <div className="flex flex-col gap-4 p-5">
        <div className="flex flex-col gap-1">
          <h2 id="crop-title" className="text-lg font-semibold">
            {t("title")}
          </h2>
          <p className="text-sm text-muted">{failed ? t("failed") : t("hint")}</p>
        </div>
        {!failed && (
          <>
            <div
              role="group"
              tabIndex={0}
              aria-label={t("area")}
              className="relative mx-auto touch-none select-none overflow-hidden rounded-2xl bg-black outline-none focus-visible:ring-2 focus-visible:ring-primary"
              style={{ width: BOX, height: BOX, cursor: loaded ? "grab" : "progress" }}
              onPointerDown={(event) => {
                if (!loaded) return;
                event.currentTarget.setPointerCapture(event.pointerId);
                drag.current = { pointer: event.pointerId, x: event.clientX, y: event.clientY, start: view };
              }}
              onPointerMove={(event) => {
                const d = drag.current;
                if (d?.pointer === event.pointerId) move({ ...d.start, x: d.start.x + event.clientX - d.x, y: d.start.y + event.clientY - d.y });
              }}
              onPointerUp={() => (drag.current = null)}
              onPointerCancel={() => (drag.current = null)}
              onWheel={(event) => zoom(view.zoom * (event.deltaY < 0 ? 1.08 : 1 / 1.08))}
              onKeyDown={(event) => {
                const steps: Record<string, [number, number]> = { ArrowLeft: [KEY_STEP, 0], ArrowRight: [-KEY_STEP, 0], ArrowUp: [0, KEY_STEP], ArrowDown: [0, -KEY_STEP] };
                const step = steps[event.key];
                if (step) move({ ...view, x: view.x + step[0], y: view.y + step[1] });
                else if (event.key === "+" || event.key === "=") zoom(view.zoom * 1.1);
                else if (event.key === "-") zoom(view.zoom / 1.1);
                else return;
                event.preventDefault();
              }}
            >
              {loaded && (
                // eslint-disable-next-line @next/next/no-img-element -- a local preview of the chosen file
                <img
                  ref={image}
                  src={loaded.url}
                  alt=""
                  draggable={false}
                  className="pointer-events-none absolute max-w-none"
                  style={{
                    width: loaded.width * scale,
                    height: loaded.height * scale,
                    left: BOX / 2 + view.x - (loaded.width * scale) / 2,
                    top: BOX / 2 + view.y - (loaded.height * scale) / 2,
                  }}
                />
              )}
              {/* The circle is what people will see; the dimmed corners fall outside it. */}
              <span aria-hidden="true" className="pointer-events-none absolute inset-0 rounded-full ring-2 ring-white/90 shadow-[0_0_0_999px_rgb(0_0_0/0.55)]" />
            </div>
            <div className="flex items-center gap-3">
              <button type="button" className="btn-ghost p-2" aria-label={t("zoomOut")} onClick={() => zoom(view.zoom / 1.2)}>
                <Minus aria-hidden="true" className="size-4" />
              </button>
              <input
                type="range"
                aria-label={t("zoom")}
                min={MIN_ZOOM}
                max={MAX_ZOOM}
                step={0.01}
                value={view.zoom}
                onChange={(event) => zoom(Number(event.target.value))}
                className="h-2 flex-1 accent-[var(--primary)]"
              />
              <button type="button" className="btn-ghost p-2" aria-label={t("zoomIn")} onClick={() => zoom(view.zoom * 1.2)}>
                <Plus aria-hidden="true" className="size-4" />
              </button>
            </div>
          </>
        )}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary px-4 py-2 text-sm" onClick={onCancel}>
            {t("cancel")}
          </button>
          {!failed && (
            <button type="button" className="btn-primary px-4 py-2 text-sm" disabled={!loaded || busy} onClick={confirm}>
              {t("use")}
            </button>
          )}
        </div>
      </div>
    </dialog>
  );
}
