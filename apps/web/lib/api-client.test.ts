import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, RoadSignalApiClient } from "./api-client";

const user = {
  id: "user-1",
  email: "driver@example.com",
  name: "Test Driver",
  role: "driver" as const,
};

function response(body: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => vi.restoreAllMocks());

describe("RoadSignalApiClient", () => {
  it("keeps credentials out of browser storage and sends bearer tokens", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(response({ access_token: "access", expires_in: 900, user }))
      .mockResolvedValueOnce(response({ items: [] }));
    const client = new RoadSignalApiClient("https://api.example.test");

    await client.login(user.email, "a secure password");
    await client.request("/api/v1/incidents");

    const headers = new Headers(fetchMock.mock.calls[1][1]?.headers);
    expect(headers.get("Authorization")).toBe("Bearer access");
    expect(fetchMock.mock.calls[0][1]?.credentials).toBe("include");
    expect(fetchMock.mock.calls[1][1]?.credentials).toBe("include");
    expect(client.session?.user).toEqual(user);
  });

  it("rotates a refresh token once and retries an unauthorized request", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(response({ access_token: "old", expires_in: 900, user }))
      .mockResolvedValueOnce(response({ detail: "expired" }, 401))
      .mockResolvedValueOnce(response({ access_token: "new", expires_in: 900 }))
      .mockResolvedValueOnce(response({ ok: true }));
    const client = new RoadSignalApiClient("https://api.example.test");

    await client.login(user.email, "a secure password");
    await expect(client.request("/api/v1/private")).resolves.toEqual({ ok: true });
    expect(new Headers(fetchMock.mock.calls[3][1]?.headers).get("Authorization")).toBe("Bearer new");
  });

  it("returns actionable validation messages", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({ detail: [{ msg: "Value error, Choose a less common password" }] }, 422),
    );
    const client = new RoadSignalApiClient("https://api.example.test");
    await expect(client.register("Test", user.email, "password1234")).rejects.toEqual(
      expect.objectContaining({ message: "Choose a less common password", status: 422 }),
    );
  });
});
