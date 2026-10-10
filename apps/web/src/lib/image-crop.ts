/** The maths behind the picture cropper (components/image-crop-dialog.tsx), kept free of the DOM
 * so it can be tested. The crop box is a square of `box` pixels; the picture sits behind it,
 * covers it at zoom 1 and can be zoomed and moved but never leaves a gap inside the box. */

export type CropView = {
  /** 1 = the picture just covers the box; larger zooms in. */
  zoom: number;
  /** How far the picture's center is from the box's center, in box pixels. */
  x: number;
  y: number;
};

export const MIN_ZOOM = 1;
export const MAX_ZOOM = 4;

/** Pixels of box per pixel of picture at zoom 1: the shorter side fills the box. */
export function coverScale(width: number, height: number, box: number): number {
  return box / Math.min(width, height);
}

export function clampView(view: CropView, width: number, height: number, box: number): CropView {
  const zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, view.zoom));
  const scale = coverScale(width, height, box) * zoom;
  const maxX = Math.max(0, (width * scale - box) / 2);
  const maxY = Math.max(0, (height * scale - box) / 2);
  return { zoom, x: Math.min(maxX, Math.max(-maxX, view.x)), y: Math.min(maxY, Math.max(-maxY, view.y)) };
}

/** Changes the zoom around the box's center, keeping the picture inside the box. */
export function zoomTo(view: CropView, zoom: number, width: number, height: number, box: number): CropView {
  const ratio = zoom / view.zoom;
  return clampView({ zoom, x: view.x * ratio, y: view.y * ratio }, width, height, box);
}

/** The square of the original picture that shows inside the box: its corner and side, in
 * picture pixels. */
export function cropSquare(view: CropView, width: number, height: number, box: number) {
  const { zoom, x, y } = clampView(view, width, height, box);
  const scale = coverScale(width, height, box) * zoom;
  const side = box / scale;
  return {
    sx: Math.max(0, width / 2 - x / scale - side / 2),
    sy: Math.max(0, height / 2 - y / scale - side / 2),
    side,
  };
}

/** A replacement name for the cropped file: same name, the extension of its new type. */
export function croppedName(name: string, type: string): string {
  const extension = type === "image/png" ? "png" : type === "image/jpeg" ? "jpg" : "webp";
  return `${name.replace(/\.[^.]+$/, "") || "picture"}.${extension}`;
}
