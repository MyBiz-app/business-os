// MapLibre 6 starts its worker from a file next to its own script, a place a bundler cannot hand
// it (the worker URL comes out empty and no map is ever drawn). So the worker and the file it
// imports are copied to public/maplibre/ before dev and build, and `loadMaplibre()` points the
// library there. The copies are not committed: they always match the installed version.
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = dirname(createRequire(join(root, "package.json")).resolve("maplibre-gl/package.json")) + "/dist";
const target = join(root, "public", "maplibre");

mkdirSync(target, { recursive: true });
for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) copyFileSync(join(dist, file), join(target, file));
