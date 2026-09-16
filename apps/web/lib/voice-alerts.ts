import { loadPreferences } from "./preferences";
import { generateVoiceboxSpeech } from "./voicebox";
import { generatePiperSpeech } from "./piper-voice";
import { deployment } from "./deployment";

const FEMALE_VOICE_HINTS = [
  "female",
  "samantha",
  "zira",
  "susan",
  "victoria",
  "karen",
  "moira",
  "tessa",
  "fiona",
  "serena",
  "allison",
  "ava",
  "aria",
  "jenny",
  "google us english",
  "google uk english female",
  "microsoft zira",
];

export function pickFemaleVoice(
  voices: Pick<SpeechSynthesisVoice, "name" | "lang">[],
): Pick<SpeechSynthesisVoice, "name" | "lang"> | null {
  if (!voices.length) return null;
  const byHint = voices.find((voice) =>
    FEMALE_VOICE_HINTS.some((hint) => voice.name.toLowerCase().includes(hint)),
  );
  if (byHint) return byHint;
  const english = voices.find((voice) => voice.lang.toLowerCase().startsWith("en"));
  return english ?? voices[0];
}

export function voiceAlertsSupported() {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

let resolvedVoice: SpeechSynthesisVoice | null = null;
let voiceResolved = false;

function resolveVoice(): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices();
  if (voices.length) {
    resolvedVoice = pickFemaleVoice(voices) as SpeechSynthesisVoice | null;
    voiceResolved = true;
  }
  return resolvedVoice;
}

if (voiceAlertsSupported()) {
  window.speechSynthesis.addEventListener("voiceschanged", resolveVoice);
}

function speakWithBrowser(text: string) {
  if (!voiceAlertsSupported() || !text) return;
  const synth = window.speechSynthesis;
  if (!voiceResolved) resolveVoice();
  const utterance = new SpeechSynthesisUtterance(text);
  if (resolvedVoice) utterance.voice = resolvedVoice;
  utterance.pitch = 1.05;
  utterance.rate = 1;
  synth.speak(utterance);
}

let currentVoiceboxAudio: HTMLAudioElement | null = null;
// Voicebox's neural TTS render takes real time; don't leave a safety alert
// unspoken while waiting on it — fall back to the instant browser voice.
const VOICEBOX_FALLBACK_MS = 4_000;

async function speakWithVoicebox(text: string, url: string, profileId: string) {
  const controller = new AbortController();
  let fallenBack = false;
  const fallbackTimer = setTimeout(() => {
    fallenBack = true;
    controller.abort();
    speakWithBrowser(text);
  }, VOICEBOX_FALLBACK_MS);
  try {
    const blob = await generateVoiceboxSpeech(url, profileId, text, controller.signal);
    clearTimeout(fallbackTimer);
    if (fallenBack) return;
    currentVoiceboxAudio?.pause();
    const audio = new Audio(URL.createObjectURL(blob));
    currentVoiceboxAudio = audio;
    void audio.play().catch(() => speakWithBrowser(text));
  } catch {
    clearTimeout(fallbackTimer);
    if (!fallenBack) speakWithBrowser(text);
  }
}

let currentPiperAudio: HTMLAudioElement | null = null;
// Piper renders at roughly a third of real time on CPU, so it is much quicker
// than Voicebox -- but a safety alert still must not wait on the network.
const PIPER_FALLBACK_MS = 3_000;

async function speakWithPiper(text: string, apiUrl: string) {
  const controller = new AbortController();
  let fallenBack = false;
  const fallbackTimer = setTimeout(() => {
    fallenBack = true;
    controller.abort();
    speakWithBrowser(text);
  }, PIPER_FALLBACK_MS);
  try {
    const blob = await generatePiperSpeech(apiUrl, text, controller.signal);
    clearTimeout(fallbackTimer);
    if (fallenBack) return;
    currentPiperAudio?.pause();
    const audio = new Audio(URL.createObjectURL(blob));
    currentPiperAudio = audio;
    void audio.play().catch(() => speakWithBrowser(text));
  } catch {
    clearTimeout(fallbackTimer);
    if (!fallenBack) speakWithBrowser(text);
  }
}

export function speakAlert(text: string) {
  if (!text) return;
  const preferences = loadPreferences();
  if (preferences.voiceEngine === "voicebox" && preferences.voiceboxProfileId) {
    void speakWithVoicebox(text, preferences.voiceboxUrl, preferences.voiceboxProfileId);
    return;
  }
  if (preferences.voiceEngine === "piper" && deployment.apiUrl) {
    void speakWithPiper(text, deployment.apiUrl);
    return;
  }
  speakWithBrowser(text);
}

export function cancelVoiceAlerts() {
  if (voiceAlertsSupported()) window.speechSynthesis.cancel();
  currentVoiceboxAudio?.pause();
  currentVoiceboxAudio = null;
  currentPiperAudio?.pause();
  currentPiperAudio = null;
}
