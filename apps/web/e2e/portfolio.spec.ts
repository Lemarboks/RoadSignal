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

const placeSuggestions = {
  type: "FeatureCollection",
  features: [
    ["Cape Town Station", "Cape Town City Centre"],
    ["Cape Town International Convention Centre", "Foreshore"],
    ["Cape Town City Hall", "Cape Town City Centre"],
    ["Cape Town Civic Centre", "Cape Town City Centre"],
    ["Cape Town Stadium", "Green Point"],
  ].map(([name, suburb], index) => ({
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates: [18.4241 + index * 0.01, -33.9249 - index * 0.01],
    },
    properties: {
      name,
      suburb,
      city: "Cape Town",
      state: "Western Cape",
      country: "South Africa",
    },
  })),
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

async function expectGeneratedLogo(page: import("@playwright/test").Page) {
  const logo = page.locator("[data-roadsignal-logo]");
  await expect(logo).toHaveCount(1);
  await expect(logo).toBeVisible();
  await expect(logo).toHaveJSProperty("complete", true);
  await expect(logo).not.toHaveJSProperty("naturalWidth", 0);
  await expect(page.locator("body")).not.toHaveText(/(^|\s)SR($|\s)/);
}

test("gates the app behind sign-in, with a guest path in", async ({ page }) => {
  await expect(page.getByRole("heading", { name: /Beyond\s+risk\.\s+Onward\./i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Fleet operations overview" })).not.toBeVisible();
  await expectGeneratedLogo(page);

  const accessibility = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(accessibility.violations).toEqual([]);

  await page.getByRole("button", { name: /Continue as guest/ }).click();
  await expect(page.getByRole("heading", { name: "Fleet operations overview" })).toBeVisible();
  await expectGeneratedLogo(page);
});

test("keeps the sign-in form on the landing screen only", async ({ page }) => {
  await enterAsGuest(page);
  await expect(page.getByRole("heading", { name: "Connect your account" })).not.toBeVisible();
  await expect(page.getByRole("link", { name: "Skip to main content" })).not.toBeFocused();

  await page.getByRole("button", { name: "Sign in", exact: true }).click();

  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in securely" })).toBeVisible();
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
  const weatherStrip = page.locator(".weather-strip");
  await expect(weatherStrip.getByText("16°C", { exact: true })).toBeVisible();
  await expect(weatherStrip.getByText("15°C", { exact: true })).toBeVisible();
  const weatherReadout = page.getByLabel("Three-point route weather model estimate");
  await expect(weatherReadout).toContainText("Rain");
  await expect(weatherReadout).toContainText("Moderate weather risk");
  await expect(weatherReadout).toContainText("16°C");
  await expect(weatherReadout).toContainText("1.2 mm");
  await expect(weatherReadout).toContainText("42 km/h");
  await expect(weatherReadout).toContainText("4.2 km");
  await expect(weatherReadout).toContainText("Origin 16°");
  await expect(weatherReadout).toContainText("Mid 16°");
  await expect(weatherReadout).toContainText("Destination 16°");
  await expect(weatherReadout).toContainText("Highest exposure: origin");
  await expect(weatherReadout).toContainText("model time 18:00");

  await page.getByRole("button", { name: "Use built-in demo routes" }).click();
  await page.getByRole("button", { name: /^Balanced Route:/ }).click();
  await page.getByRole("button", { name: "Start simulated trip" }).click();
  await expect(page.getByRole("heading", { name: "Live Trip" })).toBeVisible();
});

test("keeps location suggestions clear of the next location field", async ({ page }) => {
  await page.route("https://photon.komoot.io/api/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(placeSuggestions),
    }),
  );
  await enterAsGuest(page);
  await page.getByRole("button", { name: "Route Planner" }).click();
  await page.getByPlaceholder("Street, landmark or suburb").first().fill("Cape Town");

  const suggestions = page.locator(".place-suggestions");
  const destination = page.locator(".controls > label").filter({ hasText: "Destination" });
  await expect(suggestions.getByRole("option")).toHaveCount(5);
  const [suggestionBox, destinationBox] = await Promise.all([
    suggestions.boundingBox(),
    destination.boundingBox(),
  ]);
  expect(suggestionBox).not.toBeNull();
  expect(destinationBox).not.toBeNull();
  expect(suggestionBox!.y + suggestionBox!.height).toBeLessThanOrEqual(destinationBox!.y);
});

test("selects fallback route lines and opens incident evidence on the map", async ({ page }) => {
  await page.route("https://tiles.openfreemap.org/**", (route) => route.abort());
  await enterAsGuest(page);
  const map = page.getByRole("group", { name: "Cape Town route-risk map" }).first();

  await map.getByRole("button", { name: /Select Safest Route/ }).press("Enter");
  await expect(map.locator(".map-label strong")).toContainText("Safest Route");

  await map.getByRole("button", { name: /Accident, severity 4 of 5/ }).click();
  const detail = map.getByLabel("Accident details");
  await expect(detail).toContainText("Collision near Hospital Bend");
  await expect(detail).toContainText("86%");
});

test("opens an active driver's trip from the fleet roster", async ({ page }) => {
  await enterAsGuest(page);
  await page.getByRole("button", { name: "Fleet", exact: true }).click();
  await page.getByRole("button", { name: "View Amina Daniels's active trip" }).click();

  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  await expect(page.getByRole("heading", { name: "Amina Daniels's trip" })).toBeVisible();
  await expect(page.getByText("CA 482-771", { exact: true })).toBeVisible();
  await expect(page.getByText("Settlers Way", { exact: true })).toBeVisible();
  await expect(page.getByText("Cape Town CBD to Cape Town International Airport", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Fleet", exact: true }).click();
  await expect(page.getByRole("button", { name: "Nadia Jacobs has no active trip" })).toBeDisabled();
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
  const safestRoute = page.getByRole("button", { name: "Safest Route", exact: true });
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
  await expect(page.locator(".fleet-table").getByText("Lwazi Mbeki")).toBeVisible();
  await expect(page.locator(".fleet-table").getByText("Amina Daniels")).not.toBeVisible();

  const dimensions = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
  }));
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth + 1);
});
