import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.skip(!process.env.PLAYWRIGHT_EXTERNAL_SERVER, "These contract tests exercise the Docker build with its API enabled.");

const capability = { configured: true, available: true, model: "local-test-worker" };
const cell = {
  type: "Feature", id: "test-cell",
  geometry: { type: "Polygon", coordinates: [[[18.42, -33.92], [18.43, -33.92], [18.43, -33.93], [18.42, -33.93], [18.42, -33.92]]] },
  properties: { cell_id: "test-cell", resolution: 7, incident_count: 3, max_severity: 4, average_confidence: 0.8, latest_occurred_at: new Date().toISOString(), provenance: "demo", demo_incident_count: 3 },
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/assistant/status", route => route.fulfill({ json: {
    generation: { ...capability, available: false }, retrieval: capability, reranker: capability, transcription: capability, notice: "Test worker",
  } }));
  await page.route("**/api/v1/map/cells?**", route => route.fulfill({ json: {
    type: "FeatureCollection", features: [cell], metadata: { resolution: 7, generated_at: new Date().toISOString(), incident_count: 3, cell_count: 1, provenance: "demo", source: "active_incident_reports", includes_expired: false },
  } }));
  await page.route("**/api/v1/auth/login", route => route.fulfill({ json: {
    access_token: "contract-test-token", expires_in: 900, user: { id: "test-driver", name: "Test Driver", email: "test@example.invalid", role: "driver" },
  } }));
  await page.route("**/api/v1/incidents", route => route.request().method() === "GET"
    ? route.fulfill({ json: { items: [], total: 0 } })
    : route.fulfill({ json: { ...JSON.parse(route.request().postData() ?? "{}"), id: "test-submitted", source_type: "community", verification_status: "unverified", confidence: 0.5, occurred_at: new Date().toISOString(), expires_at: null, confirmations: 0, disputes: 0, status: "active" } }));
  await page.goto("/");
});

async function signIn(page: Page) {
  await page.getByLabel("Email", { exact: true }).fill("test@example.invalid");
  await page.getByLabel("Password", { exact: true }).fill("Test-Contract-Password-2026");
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(page.getByRole("heading", { name: "Fleet operations overview" })).toBeVisible();
  await page.getByRole("navigation", { name: "Application sections" }).getByRole("button", { name: /^Incidents/ }).click();
  await page.getByRole("button", { name: "Report incident", exact: true }).click();
}

test("map area counts expose provenance and keyboard-accessible details", async ({ page }, info) => {
  await page.getByRole("button", { name: /Continue as guest/ }).click();
  await page.getByRole("button", { name: "Risk Map", exact: true }).click();
  await page.getByRole("button", { name: "Incident areas off" }).click();
  await expect(page.getByText("3 reports across 1 areas")).toBeVisible();
  await page.getByText("Review 1 areas", { exact: true }).click();
  await page.getByRole("button", { name: /Area 1 · 3 reports/ }).click();
  await expect(page.getByRole("complementary", { name: "Incident area details" })).toContainText("Demonstration reports");
  await expect(page.getByRole("complementary", { name: "Incident area details" })).toContainText("80%");
  await page.screenshot({ path: info.outputPath("incident-areas.png"), fullPage: true });
});

test("draft review does not submit until the operator confirms", async ({ page }, info) => {
  let submitted = 0;
  page.on("request", request => { if (new URL(request.url()).pathname === "/api/v1/incidents" && request.method() === "POST") submitted++; });
  await page.route("**/api/v1/assistant/incidents/analyse", route => route.fulfill({ json: {
    mode: "fallback", retrieval_mode: "lexical", draft: { incident_type: "Pothole", severity: 2, description: "Large pothole near the station" }, duplicates: [], warnings: ["Review the location before submitting."], requires_review: true,
  } }));
  await signIn(page);
  await page.getByRole("textbox", { name: "Description", exact: true }).fill("Large pothole near the station");
  await page.getByRole("button", { name: "Help draft & check duplicates" }).click();
  await expect(page.getByRole("region", { name: "Review suggested report" })).toContainText("Rule-based draft");
  expect(submitted).toBe(0);
  await page.screenshot({ path: info.outputPath("incident-draft.png"), fullPage: true });
  const audit = await new AxeBuilder({ page }).include(".incident-composer").withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(audit.violations).toEqual([]);
  await page.getByRole("button", { name: "Apply suggested details" }).click();
  await expect(page.getByLabel("Incident type", { exact: true })).toHaveValue("Pothole");
  expect(submitted).toBe(0);
  await page.getByRole("button", { name: "Submit reviewed report" }).click();
  await expect(page.getByRole("heading", { name: "Describe what happened" })).not.toBeVisible();
  expect(submitted).toBe(1);
});

test("voice input uses multipart auth and requires transcript review", async ({ page }) => {
  let audioSent = false;
  await page.route("**/api/v1/assistant/transcribe", route => {
    audioSent = true;
    expect(route.request().headers()["content-type"]).toContain("multipart/form-data; boundary=");
    expect(route.request().headers().authorization).toBe("Bearer contract-test-token");
    return route.fulfill({ json: { text: "Pothole near Cape Town Station", language: "en", model: "test", requires_review: true } });
  });
  await signIn(page);
  await page.getByLabel("Upload incident audio").setInputFiles({ name: "report.wav", mimeType: "audio/wav", buffer: Buffer.from("RIFF-test-fixture") });
  await expect(page.getByRole("region", { name: "Review voice transcript" })).toBeVisible();
  expect(audioSent).toBe(true);
  await expect(page.getByRole("textbox", { name: "Description", exact: true })).toHaveValue("");
  await page.getByLabel("Correct the transcript").fill("Pothole near Cape Town City Hall");
  await page.getByRole("button", { name: "Use corrected transcript" }).click();
  await expect(page.getByRole("textbox", { name: "Description", exact: true })).toHaveValue("Pothole near Cape Town City Hall");
});
