// Draws every logo file from the values in src/index.ts: the SVGs in ./assets, the web favicon
// and the three Expo apps' icons. Run after changing the name, colors or mark:
//   pnpm --filter @business-os/brand build:assets
// PNGs are rendered with a headless Chromium (CHROME_PATH, or the one Playwright installs).
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { LOGO_INK, MARK, glyph, gradient, markSvg } from "../src/index.ts";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "../../..");
const assets = resolve(here, "../assets");
const font = join(root, "apps/web/src/app/(marketing)/fonts/Heebo-ExtraBold.ttf");

// The name lives in @business-os/i18n: brand.json once it exists, the English app name until then.
const i18n = join(root, "packages/i18n");
const name = existsSync(join(i18n, "brand.json"))
  ? JSON.parse(readFileSync(join(i18n, "brand.json"), "utf8")).name
  : JSON.parse(readFileSync(join(i18n, "messages/en.json"), "utf8")).app.name;
// The wordmark colors the last capitalised word ("Biz" in "MyBiz"); a name without one stays in ink.
const [, lead, accent] = /^(.+?)([A-Z][^A-Z]*)$/.exec(name) ?? [null, name, ""];

/** The M alone on a transparent canvas, scaled into the middle (Android adaptive and monochrome). */
function glyphSvg({ ink, core, scale }) {
  const s = MARK.size;
  const inset = (s - s * scale) / 2;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${s} ${s}" fill="none"><defs>${gradient("g")}</defs>` +
    `<g transform="translate(${inset} ${inset}) scale(${scale})">${glyph({ ink, core })}</g></svg>`;
}

/** The tile at a third of the canvas, as the launch screen shows it. */
const splashSvg = () =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192"><svg x="64" y="64" width="64" height="64">${markSvg()}</svg></svg>`;

const backgroundSvg = () =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs>${gradient("g")}</defs><rect width="64" height="64" fill="url(#g)"/></svg>`;

/** Horizontal logo: the mark, then "My" in ink and "Biz" in the gradient. */
function wordmarkSvg(ink) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 64" fill="none"><defs>${gradient("g")}` +
    `${gradient("t", 'gradientUnits="userSpaceOnUse" x1="150" y1="0" x2="250" y2="0"')}</defs>` +
    `<rect width="64" height="64" rx="${MARK.tileRadius}" fill="url(#g)"/>${glyph({ ink: "#FFFFFF", core: "url(#g)" })}` +
    `<text x="80" y="47" font-family="Heebo, Arial, Helvetica, sans-serif" font-size="44" font-weight="800" letter-spacing="-0.5" fill="${ink}">` +
    `${lead}<tspan fill="url(#t)">${accent}</tspan></text></svg>`;
}

const chrome = process.env.CHROME_PATH ??
  ["/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell", "/usr/bin/chromium", "/usr/bin/google-chrome"].find(existsSync);
if (!chrome) throw new Error("Set CHROME_PATH to a Chrome or Chromium binary to render the PNGs.");
const work = mkdtempSync(join(tmpdir(), "brand-"));

/** Renders an SVG to a `size` x `size` PNG (transparent unless the SVG fills it). */
function png(svg, size, out) {
  const page = join(work, "page.html");
  writeFileSync(page, `<!doctype html><style>@font-face{font-family:Heebo;src:url("file://${font}")}` +
    `html,body{margin:0;background:transparent}body>svg{display:block;width:${size}px;height:${size}px}</style>${svg}`);
  execFileSync(chrome, ["--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
    "--default-background-color=00000000", `--window-size=${size},${size}`, `--screenshot=${out}`, `file://${page}`], { stdio: "ignore" });
  return readFileSync(out);
}

/** A .ico that wraps PNG images (supported by every current browser). */
function ico(images) {
  const header = Buffer.alloc(6 + 16 * images.length);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(images.length, 4);
  let offset = header.length;
  images.forEach(({ size, data }, i) => {
    const entry = 6 + 16 * i;
    header.writeUInt8(size >= 256 ? 0 : size, entry);
    header.writeUInt8(size >= 256 ? 0 : size, entry + 1);
    header.writeUInt16LE(1, entry + 4);
    header.writeUInt16LE(32, entry + 6);
    header.writeUInt32LE(data.length, entry + 8);
    header.writeUInt32LE(offset, entry + 12);
    offset += data.length;
  });
  return Buffer.concat([header, ...images.map(({ data }) => data)]);
}

// Source SVGs, for documents, emails and designers.
writeFileSync(join(assets, "mark.svg"), markSvg() + "\n");
writeFileSync(join(assets, "logo-on-light.svg"), wordmarkSvg(LOGO_INK.light) + "\n");
writeFileSync(join(assets, "logo-on-dark.svg"), wordmarkSvg(LOGO_INK.dark) + "\n");

// Web: SVG favicon, .ico fallback and the home-screen icon for iPhones.
const web = join(root, "apps/web/src/app");
writeFileSync(join(web, "icon.svg"), markSvg() + "\n");
writeFileSync(join(web, "favicon.ico"), ico([16, 32, 48].map((size) => ({ size, data: png(markSvg(), size, join(work, `f${size}.png`)) }))));
png(markSvg({ radius: 0 }), 180, join(web, "apple-icon.png"));

// Expo apps: the stores mask the icon themselves, so it is a full square.
for (const app of ["client-app", "business-app", "staff-app"]) {
  const dir = join(root, "apps", app, "assets");
  png(markSvg({ radius: 0 }), 1024, join(dir, "icon.png"));
  png(markSvg(), 48, join(dir, "favicon.png"));
  png(splashSvg(), 1024, join(dir, "splash-icon.png"));
  png(glyphSvg({ ink: "#FFFFFF", core: null, scale: 0.8 }), 512, join(dir, "android-icon-foreground.png"));
  png(backgroundSvg(), 512, join(dir, "android-icon-background.png"));
  png(glyphSvg({ ink: "#FFFFFF", core: null, scale: 0.8 }), 432, join(dir, "android-icon-monochrome.png"));
}

console.log("Logo files written.");
