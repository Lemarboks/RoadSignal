import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const weatherResponse = {
  current: {
    time: "2026-08-11T18:00",
    temperature_2m: 16.2,
    apparent_temperature: 15.1,
    precipitation: 1.2,
    weather_code: 61,
    wind_speed_10m: 42,
    visibility: 4200,
  },
};

test.beforeEach(async ({ page }) => {
  await page.route("**/v1/forecast?**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(weatherResponse) }),
  );
  await page.goto("/");
});

test("exposes data provenance and keyboard navigation", async ({ page }) => {
  await expect(page.getByRole("heading", { name: "Fleet operations overview" })).toBeVisible();
  await expect(page.getByText("Demo data", { exact: true })).toBeVisible();
  await expect(page.getByText(/decision support, not a guarantee of safety/i)).toBeVisible();

  await page.keyboard.press("Tab");
  const skipLink = page.getByRole("link", { name: "Skip to main content" });
  await expect(skipLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
});

test("shows Celsius weather and supports the demonstration trip flow", async ({ page }) => {
  await page.getByRole("button", { name: "Route Planner" }).click();
  await expect(page.getByRole("heading", { name: "Route Planner" })).toBeVisible();
  await expect(page.getByText("16°C", { exact: true })).toBeVisible();
  await expect(page.getByText("15°C", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Use built-in demo routes" }).click();
  await page.getByRole("button", { name: /Balanced Route/ }).click();
  await page.getByRole("button", { name: "Start simulated trip" }).click();
  await expect(page.getByRole("heading", { name: "Live Trip" })).toBeVisible();
});

test("has no automatically detectable WCAG A or AA violations", async ({ page }) => {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations).toEqual([]);
});

test("does not overflow the viewport", async ({ page }) => {
  await page.getByRole("button", { name: "Incidents" }).click();
  const dimensions = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
  }));
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth + 1);
});
