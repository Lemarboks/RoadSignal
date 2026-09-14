import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.use({ launchOptions: { args: ["--enable-unsafe-swiftshader"] } });

test.beforeEach(async ({ page }) => {
  // Exercise the fully functional offline-map path without third-party requests.
  await page.route("https://tiles.openfreemap.org/**", (route) => route.abort());
  await page.route("**/v1/forecast?**", (route) => route.abort());
  await page.goto("/");
  await page.getByRole("button", { name: /Continue as guest/ }).click();
  await page.getByRole("button", { name: "Open fleet replay" }).click();
  await expect(page.getByRole("heading", { name: "Fleet replay" })).toBeVisible();
});

test("demo trackers move, pause, reset and expose offline telemetry", async ({ page }, info) => {
  const monitor = page.locator(".fleet-monitor");
  await monitor.scrollIntoViewIfNeeded();
  const position = page.getByLabel("Selected demo vehicle coordinates");
  const initial = await position.textContent();
  await expect(position).not.toHaveText(initial!);
  await page.getByRole("button", { name: "Pause demo replay" }).click();
  const paused = await position.textContent();
  await page.waitForTimeout(1200);
  await expect(position).toHaveText(paused!);
  await page.getByRole("button", { name: "Reset replay" }).click();
  await expect(page.getByLabel("Demo elapsed time")).toHaveAttribute("data-seconds", "0");
  await page.getByLabel("Demo playback speed").selectOption("4");
  await expect(page.getByLabel("Demo playback speed")).toHaveValue("4");
  await page.getByRole("list", { name: "Demo vehicle trackers" }).getByRole("button", { name: /CA 614-208/ }).click();
  const inspector = page.getByRole("region", { name: "Selected device details" });
  await expect(inspector).toContainText("Offline · last known position");
  await expect(inspector).toContainText("Unavailable");
  await page.getByRole("list", { name: "Demo vehicle trackers" }).getByRole("button", { name: /CA 482-771/ }).click();
  await page.getByRole("button", { name: "Demo tracker CA 193-044, moving", exact: true }).press("Enter");
  await expect(inspector).toContainText("Lwazi Mbeki");
  // Isolate the component from the global sticky navigation when capturing a
  // panel taller than the viewport. Normal interaction assertions keep it visible.
  await monitor.screenshot({ path: info.outputPath("fleet-replay.png"), style: ".shell > aside { visibility: hidden !important; }" });
  const audit = await new AxeBuilder({ page }).include(".fleet-monitor").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(audit.violations).toEqual([]);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  expect(overflow).toBe(false);
});

test("street sensors are explicitly synthetic and stale readings stay identifiable", async ({ page }, info) => {
  await page.getByRole("button", { name: "Pause demo replay" }).click();
  await page.getByRole("button", { name: "Street sensors 3" }).click();
  await page.getByRole("list", { name: "Demo street sensors" }).getByRole("button", { name: /Athlone station/ }).click();
  const inspector = page.getByRole("region", { name: "Selected device details" });
  await expect(inspector).toContainText("Street-level sensor simulation");
  await expect(inspector).toContainText("Road surface");
  await expect(inspector).toContainText("Mean traffic speed");
  await expect(inspector).toContainText("No physical sensor is connected");
  await page.locator(".fleet-monitor").screenshot({ path: info.outputPath("street-sensors.png"), style: ".shell > aside { visibility: hidden !important; }" });
  await page.getByRole("button", { name: "Demo sensor Airport approach station, stale", exact: true }).press("Enter");
  await expect(inspector).toContainText("Stale · last sample retained");
  await expect(inspector).toContainText("Readings are frozen, not current");
});

test("reduced motion starts paused and navigation to a driver's trip still works", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.getByRole("button", { name: "Play demo replay" })).toBeVisible();
  await expect(page.locator(".fleet-monitor")).toHaveAttribute("data-playing", "false");
  await expect(page.getByText("Reduced motion is on.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Play demo replay" }).click();
  await expect(page.locator(".fleet-monitor")).toHaveAttribute("data-playing", "false");
  await page.getByRole("button", { name: "Open driver’s demo trip" }).click();
  await expect(page.getByRole("heading", { name: "Amina Daniels's trip" })).toBeVisible();
});

test("MapLibre device markers work with a deterministic street-style fixture", async ({ page }, info) => {
  await page.unroute("https://tiles.openfreemap.org/**");
  await page.route("https://tiles.openfreemap.org/**", (route) => route.fulfill({ json: {
    version: 8, sources: {}, layers: [{ id: "ground", type: "background", paint: { "background-color": "#e8ece8" } }],
  } }));
  await page.reload();
  await page.getByRole("button", { name: /Continue as guest/ }).click();
  await page.getByRole("button", { name: "Open fleet replay" }).click();
  await expect(page.locator(".telemetry-map .maplibre-canvas")).toHaveClass(/is-ready/, { timeout: 15000 });
  await expect(page.locator(".telemetry-marker")).toHaveCount(7);
  await expect(page.locator(".telemetry-marker.maplibregl-marker")).toHaveCount(7);
  await expect(page.locator(".telemetry-marker").first()).toHaveCSS("position", "absolute");
  await page.getByRole("button", { name: "Demo tracker CA 614-208, offline", exact: true }).click();
  await expect(page.getByRole("region", { name: "Selected device details" })).toContainText("Offline · last known position");
  await expect(page.locator(".telemetry-marker.offline")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".telemetry-marker.offline")).toHaveCSS("background-color", "rgb(242, 197, 0)");
  await page.getByRole("button", { name: "Demo sensor Athlone station, reporting", exact: true }).click();
  await expect(page.getByRole("region", { name: "Selected device details" })).toContainText("Athlone station");
  await page.getByRole("button", { name: "Pause demo replay" }).click();
  await page.locator(".fleet-monitor").screenshot({ path: info.outputPath("maplibre-devices.png"), style: ".shell > aside { visibility: hidden !important; }" });
});
