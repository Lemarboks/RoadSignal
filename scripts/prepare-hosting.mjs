import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { resolve } from "node:path";

const source = resolve("apps/web/out");
const destination = resolve("dist");
const clientDestination = resolve("dist/client");

if (!existsSync(source)) {
  throw new Error(`Static web output was not found at ${source}`);
}

rmSync(destination, { recursive: true, force: true });
mkdirSync(clientDestination, { recursive: true });
mkdirSync(resolve("dist/server"), { recursive: true });
mkdirSync(resolve("dist/.openai"), { recursive: true });
cpSync(source, clientDestination, { recursive: true });
cpSync(resolve("infrastructure/sites/static-worker.js"), resolve("dist/server/index.js"));
cpSync(resolve(".openai/hosting.json"), resolve("dist/.openai/hosting.json"));
console.log("Prepared Sites worker and static assets in dist/");
