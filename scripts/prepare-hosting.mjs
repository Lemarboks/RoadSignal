import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { resolve } from "node:path";

const source = resolve("apps/web/out");
const destination = resolve("dist");

if (!existsSync(source)) {
  throw new Error(`Static web output was not found at ${source}`);
}

rmSync(destination, { recursive: true, force: true });
mkdirSync(destination, { recursive: true });
cpSync(source, destination, { recursive: true });
console.log("Prepared static production artifact in dist/");
