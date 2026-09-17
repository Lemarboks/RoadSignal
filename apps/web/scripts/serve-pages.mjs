// Serve the real static artifact at its repository path, including honest 404s.
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(fileURLToPath(new URL("../out/", import.meta.url)));
const base = (process.env.ROADSIGNAL_PAGES_BASE_PATH ?? "/RoadSignal").replace(/\/$/, "");
const port = Number(process.env.PLAYWRIGHT_PORT ?? 4173);
const mime = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json", ".txt": "text/plain; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml", ".woff2": "font/woff2", ".ico": "image/x-icon" };

const server = createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
    if (base && pathname === base) { response.writeHead(308, { Location: `${base}/` }).end(); return; }
    if (!pathname.startsWith(`${base}/`)) { response.writeHead(404).end(); return; }
    let target = path.resolve(root, `.${pathname.slice(base.length)}`);
    if ((target !== root && !target.startsWith(`${root}${path.sep}`)) || pathname.includes("\0")) { response.writeHead(404).end(); return; }
    if ((await stat(target)).isDirectory()) target = path.join(target, "index.html");
    response.writeHead(200, { "Content-Type": mime[path.extname(target)] ?? "application/octet-stream" });
    response.end(await readFile(target));
  } catch { response.writeHead(404).end(); }
});
server.listen(port, "127.0.0.1", () => console.log(`Static Pages preview: http://127.0.0.1:${port}${base}/`));
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => server.close(() => process.exit(0)));
