import { describe, expect, it } from "vitest";
import { pickFemaleVoice } from "./voice-alerts";

describe("pickFemaleVoice", () => {
  it("returns null when no voices are available", () => {
    expect(pickFemaleVoice([])).toBeNull();
  });

  it("prefers a voice whose name matches a known female voice", () => {
    const voices = [
      { name: "Google UK English Male", lang: "en-GB" },
      { name: "Microsoft Zira - English (United States)", lang: "en-US" },
      { name: "Google US English", lang: "en-US" },
    ];
    expect(pickFemaleVoice(voices)?.name).toBe("Microsoft Zira - English (United States)");
  });

  it("falls back to any English voice when no female match exists", () => {
    const voices = [
      { name: "Google Deutsch", lang: "de-DE" },
      { name: "Google US English", lang: "en-US" },
    ];
    expect(pickFemaleVoice(voices)?.name).toBe("Google US English");
  });

  it("falls back to the first voice when nothing else matches", () => {
    const voices = [
      { name: "Google Deutsch", lang: "de-DE" },
      { name: "Google Francais", lang: "fr-FR" },
    ];
    expect(pickFemaleVoice(voices)?.name).toBe("Google Deutsch");
  });
});
