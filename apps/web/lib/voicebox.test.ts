import { afterEach, describe, expect, it, vi } from "vitest";
import { generateVoiceboxSpeech, listVoiceboxProfiles, testVoiceboxConnection, VoiceboxError } from "./voicebox";

afterEach(() => vi.unstubAllGlobals());

describe("testVoiceboxConnection", () => {
  it("returns true when the health endpoint responds ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 200 })));
    await expect(testVoiceboxConnection("http://127.0.0.1:17493")).resolves.toBe(true);
  });

  it("returns false when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network error")));
    await expect(testVoiceboxConnection("http://127.0.0.1:17493")).resolves.toBe(false);
  });

  it("returns false on a non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 503 })));
    await expect(testVoiceboxConnection("http://127.0.0.1:17493")).resolves.toBe(false);
  });
});

describe("listVoiceboxProfiles", () => {
  it("normalises a plain array response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify([{ id: "abc", name: "Morgan" }, { id: "def" }]), { status: 200 }),
      ),
    );
    const profiles = await listVoiceboxProfiles("http://127.0.0.1:17493");
    expect(profiles).toEqual([
      { id: "abc", name: "Morgan" },
      { id: "def", name: "def" },
    ]);
  });

  it("throws a VoiceboxError on a non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 500 })));
    await expect(listVoiceboxProfiles("http://127.0.0.1:17493")).rejects.toBeInstanceOf(VoiceboxError);
  });
});

describe("generateVoiceboxSpeech", () => {
  it("generates then fetches the resulting audio blob", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "gen-1" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(new Blob(["audio"]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const blob = await generateVoiceboxSpeech("http://127.0.0.1:17493/", "profile-1", "Turn left");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:17493/generate",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ profile_id: "profile-1", text: "Turn left", language: "en" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(2, "http://127.0.0.1:17493/audio/gen-1", expect.anything());
    expect(blob).toBeInstanceOf(Blob);
  });

  it("throws when generation fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 422 })));
    await expect(
      generateVoiceboxSpeech("http://127.0.0.1:17493", "profile-1", "Turn left"),
    ).rejects.toBeInstanceOf(VoiceboxError);
  });
});
