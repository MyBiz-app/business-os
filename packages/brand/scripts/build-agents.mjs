// Draws the AI agents' avatars from src/agents.ts: an SVG (fallback) and a WebP per face in
// ./agents. Run after changing a look:  pnpm --filter @business-os/brand build:agents
// WebP is rendered with headless Chromium (CHROME_PATH, or the one Playwright installs) and
// converted with Python's Pillow.
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { ALL_AVATARS, avatarSvg } from "../src/agents.ts";

const out = resolve(dirname(fileURLToPath(import.meta.url)), "../agents");
const chrome = process.env.CHROME_PATH ??
  ["/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell", "/usr/bin/chromium", "/usr/bin/google-chrome"].find(existsSync);
if (!chrome) throw new Error("Set CHROME_PATH to a Chrome or Chromium binary to render the WebP files.");
const work = mkdtempSync(join(tmpdir(), "agents-"));

for (const avatar of ALL_AVATARS) {
  const svg = avatarSvg(avatar);
  writeFileSync(join(out, `${avatar.key}.svg`), svg + "\n");
  const page = join(work, "page.html");
  const shot = join(work, `${avatar.key}.png`);
  writeFileSync(page, `<!doctype html><style>html,body{margin:0;background:transparent}svg{display:block;width:256px;height:256px}</style>${svg}`);
  execFileSync(chrome, ["--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
    "--default-background-color=00000000", "--window-size=256,256", `--screenshot=${shot}`, `file://${page}`], { stdio: "ignore" });
  execFileSync("python3", ["-I", "-c", "import sys;from PIL import Image;Image.open(sys.argv[1]).save(sys.argv[2],'WEBP',quality=88,method=6)", shot, join(out, `${avatar.key}.webp`)]);
}
console.log(`Wrote ${ALL_AVATARS.length} avatars to ${out}`);
