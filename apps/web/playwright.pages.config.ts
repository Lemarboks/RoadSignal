import { defineConfig, devices } from "@playwright/test";

const port = process.env.PLAYWRIGHT_PORT ?? "4173";
const basePath = process.env.ROADSIGNAL_PAGES_BASE_PATH ?? "/RoadSignal";

export default defineConfig({
  testDir: "./pages-tests",
  workers: 1,
  retries: 0,
  timeout: 45_000,
  reporter: "list",
  outputDir: "test-results/pages",
  use: {
    baseURL: `http://127.0.0.1:${port}${basePath}/`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: { args: ["--enable-unsafe-swiftshader"], ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : {}) },
  },
  projects: [
    { name: "pages-desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "pages-mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    command: "node scripts/serve-pages.mjs",
    url: `http://127.0.0.1:${port}${basePath}/`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
