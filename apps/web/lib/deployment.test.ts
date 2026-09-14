import { describe, expect, it } from "vitest";
import { resolveDeployment } from "./deployment";

describe("deployment modes", () => {
  it("keeps Docker same-origin and development backends available", () => {
    expect(resolveDeployment({ apiUrl: "/" })).toMatchObject({ backendEnabled: true, apiUrl: "", demoOnly: false });
    expect(resolveDeployment({ nodeEnv: "development" }).apiUrl).toBe("http://localhost:8000");
  });
  it("serves a backend-free Pages demo by default", () => {
    expect(resolveDeployment({ githubPages: true, nodeEnv: "development" })).toMatchObject({ backendEnabled: false, apiUrl: "", demoOnly: true });
  });
  it("accepts an explicitly configured HTTPS backend", () => {
    expect(resolveDeployment({ githubPages: true, apiUrl: "https://api.example.org/" })).toMatchObject({ backendEnabled: true, apiUrl: "https://api.example.org", demoOnly: false });
  });
  it.each(["/", "//example.org", "http://api.example.org", "https://localhost:8000", "https://127.0.0.1", "https://[::1]", "https://operator:secret@api.example.org", "https://api.example.org?token=secret", "not a URL"])("fails closed for unsuitable Pages API URL %s", (apiUrl) => {
    expect(resolveDeployment({ githubPages: true, apiUrl })).toMatchObject({ backendEnabled: false, apiUrl: "", demoOnly: true });
  });
});
