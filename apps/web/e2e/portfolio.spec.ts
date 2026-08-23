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

async function enterAsGuest(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: /Continue as guest/ }).click();
}

test("gates the app behind sign-in, with a guest path in", async ({ page }) => {
  await expect(page.getByRole("heading", { name: /Beyond\s+risk\.\s+Onward\./i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Fleet operations overview" })).not.toBeVisible();

  const accessibility = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(accessibility.violations).toEqual([]);

  await page.getByRole("button", { name: /Continue as guest/ }).click();
  await expect(page.getByRole("heading", { name: "Fleet operations overview" })).toBeVisible();
});

test("exposes data provenance and keyboard navigation", async ({ page }) => {
  await enterAsGuest(page);
  await expect(page.getByRole("heading", { name: "Fleet operations overview" })).toBeVisible();
  await expect(page.getByText("Demo data", { exact: true })).toBeVisible();
  await expect(page.getByText(/decision support, not a guarantee of safety/i)).toBeVisible();

  // next dev's devtools overlay (<nextjs-portal>, absent in production) can
  // grab the first Tab stop once it has had time to initialise -- which by
  // this point in the test it has. It's dev-only noise, not part of the
  // app's real tab order, so drop it before asserting on keyboard nav.
  await page.evaluate(() => document.querySelector("nextjs-portal")?.remove());
  await page.keyboard.press("Tab");
  const skipLink = page.getByRole("link", { name: "Skip to main content" });
  await expect(skipLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
});

test("shows Celsius weather and supports the demonstration trip flow", async ({ page }) => {
  await enterAsGuest(page);
  await page.getByRole("button", { name: "Route Planner" }).click();
  await expect(page.getByRole("heading", { name: "Route Planner" })).toBeVisible();
  await expect(page.getByText("16°C", { exact: true })).toBeVisible();
  await expect(page.getByText("15°C", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Use built-in demo routes" }).click();
  await page.getByRole("button", { name: /Balanced Route/ }).click();
  await page.getByRole("button", { name: "Start simulated trip" }).click();
  await expect(page.getByRole("heading", { name: "Live Trip" })).toBeVisible();
});

test("explains the risk evidence and blocked training decision", async ({ page }) => {
  await enterAsGuest(page);
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Risk evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "No trained safety model" })).toBeVisible();
  await expect(page.getByText("Training gate").first()).toBeVisible();
  await expect(page.getByText("Blocked", { exact: true })).toBeVisible();
  await expect(page.getByText(/synthetic holdout cannot establish real-world accuracy/i)).toBeVisible();

  const accessibility = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(accessibility.violations).toEqual([]);

  const dimensions = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
  }));
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth + 1);
});
test("has no automatically detectable WCAG A or AA violations", async ({ page }) => {
  await enterAsGuest(page);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations).toEqual([]);
});

test("does not overflow the viewport", async ({ page }) => {
  await enterAsGuest(page);
  await page.getByRole("button", { name: "Incidents" }).click();
  const dimensions = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
  }));
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth + 1);
});

test("renders distinct risk map, analytics, and fleet workspaces", async ({ page }) => {
  await enterAsGuest(page);

  await page.getByRole("button", { name: "Risk Map" }).click();
  await expect(page.getByRole("heading", { name: "Network risk map" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Areas to review" })).toBeVisible();
  const safestRoute = page.getByRole("button", { name: "Safest Route" });
  await safestRoute.click();
  await expect(safestRoute).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText(/\d+\/100 estimate/)).toBeVisible();

  await page.getByRole("button", { name: "Analytics" }).click();
  await expect(page.getByRole("heading", { name: "Performance analytics" })).toBeVisible();
  await page.getByRole("button", { name: "7 days" }).click();
  await expect(page.getByRole("button", { name: "7 days" })).toHaveAttribute("aria-pressed", "true");

  await page.getByRole("button", { name: "Fleet", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Fleet roster" })).toBeVisible();
  await page.getByPlaceholder("Search driver, vehicle or route").fill("Lwazi");
  await expect(page.getByText("Lwazi Mbeki")).toBeVisible();
  await expect(page.getByText("Amina Daniels")).not.toBeVisible();

  const dimensions = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
  }));
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth + 1);
});
