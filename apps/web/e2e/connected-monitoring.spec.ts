import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

function snapshot() {
  const now = new Date().toISOString();
  return { source: "demo", generated_at: now, notice: "Synthetic server packets", alerts: [
    { id: "alert-1", kind: "stale_device", device_id: "S1", source: "demo", status: "open", opened_at: now, resolved_at: null, message: "Sensor packets are stale." },
  ], automation: { configured: true, last_run_at: now, last_run_key: "health-check", run_count: 7 }, devices: [
    { id: "CA 482-771", kind: "vehicle", label: "Tracker one", source: "demo", state: "moving", reported_at: now, received_at: now, latitude: -33.95, longitude: 18.55, age_seconds: 0, is_stale: false, readings: { speedKmh: 44, heading: 90, battery: 82 } },
    { id: "S1", kind: "sensor", label: "Woodstock station", source: "demo", state: "stale", reported_at: now, received_at: now, latitude: -33.93, longitude: 18.44, age_seconds: 360, is_stale: true, readings: { airC: 18.2 } },
  ] };
}

test.beforeEach(async ({ page }) => {
  await page.route("https://tiles.openfreemap.org/**", (route) => route.abort());
  await page.route("**/v1/forecast?**", (route) => route.abort());
  await page.goto("/");
  await page.getByRole("button", { name: /Continue as guest/ }).click();
  await page.getByRole("button", { name: "Open fleet replay" }).click();
});

test("connected demo uses server packets and keeps automation and review provenance clear", async ({ page }) => {
  await page.route("**/api/v1/monitoring", (route) => route.fulfill({ json: snapshot() }));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.getByRole("button", { name: "Connected demo", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Connected demo fleet" })).toBeVisible();
  await expect(page.getByRole("group", { name: "Demo replay controls" })).toHaveCount(0);
  await expect(page.getByLabel("Selected demo vehicle coordinates")).toHaveText("-33.95000, 18.55000");
  await expect(page.getByRole("button", { name: "Vehicle trackers 1" })).toBeVisible();
  await expect(page.locator(".fleet-monitor")).toHaveAttribute("data-playing", "false");
  await page.getByRole("button", { name: "Street sensors 1" }).click();
  const inspector = page.getByRole("region", { name: "Selected device details" });
  await expect(inspector).toContainText("Stale · last sample retained");
  await expect(inspector).toContainText("Unavailable");
  const automation = page.getByRole("region", { name: "Monitoring automation" });
  await expect(automation).toContainText("Sensor packets are stale.");
  await expect(automation).toContainText("No automatic incident publication");
  await page.getByText("Evidence review inbox", { exact: true }).click();
  await expect(automation).toContainText("Sign in as an incident moderator or administrator");
  await expect(page.getByRole("button", { name: "Approve evidence review" })).toHaveCount(0);
  const audit = await new AxeBuilder({ page }).include(".fleet-monitor").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(audit.violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1)).toBe(false);
  await page.getByRole("button", { name: "Local replay", exact: true }).click();
  await expect(page.getByRole("button", { name: "Vehicle trackers 4" })).toBeVisible();
  await expect(page.getByRole("group", { name: "Demo replay controls" })).toBeVisible();
});

test("lost connection retains only last known server positions and suppresses current speed", async ({ page }) => {
  let available = true;
  await page.route("**/api/v1/monitoring", (route) => available ? route.fulfill({ json: snapshot() }) : route.fulfill({ status: 503, json: { detail: "Offline" } }));
  await page.getByRole("button", { name: "Connected demo", exact: true }).click();
  await expect(page.getByLabel("Selected demo vehicle coordinates")).toHaveText("-33.95000, 18.55000");
  available = false;
  await page.getByRole("button", { name: "Refresh connection", exact: true }).click();
  await expect(page.locator(".connected-status")).toContainText("Connection lost");
  await expect(page.getByLabel("Selected demo vehicle coordinates")).toHaveText("-33.95000, 18.55000");
  await expect(page.getByRole("region", { name: "Selected device details" })).toContainText("Offline · last known position");
  await expect(page.getByRole("region", { name: "Selected device details" })).toContainText("Unavailable");
});

test("denied connection shows no replay devices in connected mode", async ({ page }) => {
  await page.route("**/api/v1/monitoring", (route) => route.fulfill({ status: 401, json: { detail: "Sign in required" } }));
  await page.getByRole("button", { name: "Connected demo", exact: true }).click();
  await expect(page.locator(".connected-status")).toContainText("Sign in to access connected monitoring");
  await expect(page.getByRole("button", { name: "Vehicle trackers 0" })).toBeVisible();
  await expect(page.getByLabel("Selected demo vehicle coordinates")).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Selected device details" })).toContainText("No connected devices received");
});
