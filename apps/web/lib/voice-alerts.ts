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

export function speakAlert(text: string) {
  if (!voiceAlertsSupported() || !text) return;
  const synth = window.speechSynthesis;
  if (!voiceResolved) resolveVoice();
  const utterance = new SpeechSynthesisUtterance(text);
  if (resolvedVoice) utterance.voice = resolvedVoice;
  utterance.pitch = 1.05;
  utterance.rate = 1;
  synth.speak(utterance);
}

export function cancelVoiceAlerts() {
  if (voiceAlertsSupported()) window.speechSynthesis.cancel();
}
