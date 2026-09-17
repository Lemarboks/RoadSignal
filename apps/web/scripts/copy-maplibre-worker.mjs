/**
 * Stage the MapLibre worker into public/ so it can be served as a pair.
 *
 * MapLibre v6 is ESM-only and its worker does a *relative* import of a sibling
 * chunk (maplibre-gl-shared.mjs, ~500KB). Webpack's `new URL(..., import.meta.url)`
 * asset handling emits the 19KB worker on its own and leaves the sibling behind,
 * so the worker 404s on load, never starts, and the map silently falls back to
 * the schematic view with no error surfaced anywhere.
 *
 * Copying both files side by side keeps the relative import intact, and serving
 * them from public/ means the URL survives `output: "export"` and the GitHub
 * Pages basePath without depending on bundler asset resolution at all.
 */
import { copyFileSync, mkdirSync, existsSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";

const require = createRequire(import.meta.url);
const FILES = ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"];

const distDir = dirname(require.resolve("maplibre-gl/dist/maplibre-gl-worker.mjs"));
const outDir = join(process.cwd(), "public", "maplibre");
mkdirSync(outDir, { recursive: true });

let copied = 0;
for (const name of FILES) {
  const from = join(distDir, name);
  if (!existsSync(from)) {
    console.error(`[maplibre-worker] missing ${name} in ${distDir}`);
    process.exit(1);
  }
  const to = join(outDir, name);
  copyFileSync(from, to);
  copied += 1;
  console.log(`[maplibre-worker] ${name} -> public/maplibre/ (${(statSync(to).size / 1024).toFixed(0)}KB)`);
}
if (copied !== FILES.length) {
  console.error("[maplibre-worker] expected to copy the worker and its sibling chunk");
  process.exit(1);
}
