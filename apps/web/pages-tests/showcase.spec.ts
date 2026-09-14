import { expect, test } from "@playwright/test";

test("Pages artifact loads assets, runs the guest showcase and never calls a missing backend", async ({ page }, info) => {
  const apiRequests: string[] = [];
  const failures: string[] = [];
  const hasBackend = Boolean(process.env.NEXT_PUBLIC_API_URL?.trim());
  page.on("pageerror", (error) => failures.push(error.message));
  page.on("response", (response) => {
    if (response.url().includes("/_next/") && response.status() >= 400) failures.push(`Asset ${response.status()}: ${response.url()}`);
  });
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.includes("/api/v1/")) { apiRequests.push(url.pathname); await route.fulfill({ status: 503, json: { detail: "No backend in static artifact test" } }); return; }
    if (url.hostname !== "127.0.0.1") { await route.abort(); return; }
    await route.continue();
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("./");
  await expect(page.getByRole("button", { name: /Continue as guest/ })).toBeVisible();
  if (!hasBackend) {
    await expect(page.getByRole("heading", { name: "Explore RoadSignal" })).toBeVisible();
    await expect(page.locator('input[type="password"]')).toHaveCount(0);
  }
  const icon = page.locator('link[rel="icon"]').first();
  const iconUrl = await icon.getAttribute("href");
  expect(iconUrl).toBeTruthy();
  expect((await page.request.get(new URL(iconUrl!, page.url()).href)).status()).toBe(200);
  await page.screenshot({ path: info.outputPath("pages-entry.png"), fullPage: true });
  await page.getByRole("button", { name: /Continue as guest/ }).click();
  await page.getByRole("button", { name: "Open fleet replay" }).click();
  await expect(page.getByRole("heading", { name: "Fleet replay" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Vehicle trackers 4" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Street sensors 3" })).toBeVisible();
  if (!hasBackend) {
    await expect(page.getByRole("button", { name: "Connected demo", exact: true })).toBeDisabled();
    await expect(page.getByText("Connected monitoring needs the Docker services", { exact: false })).toBeVisible();
    await expect(page.locator('a[href^="http://localhost"]')).toHaveCount(0);
  }
  await page.getByRole("button", { name: "Street sensors 3" }).click();
  await expect(page.getByRole("region", { name: "Selected device details" })).toContainText("No physical sensor is connected");
  await page.locator(".fleet-monitor").screenshot({ path: info.outputPath("pages-fleet.png"), style: ".shell > aside { visibility: hidden !important; }" });
  await page.getByRole("button", { name: "Vehicle trackers 4" }).click();
  await page.getByRole("button", { name: "Open driver’s demo trip" }).click();
  await expect(page.getByRole("heading", { name: "Amina Daniels's trip" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1)).toBe(false);
  expect(failures).toEqual([]);
  if (!hasBackend) expect(apiRequests).toEqual([]);
});
