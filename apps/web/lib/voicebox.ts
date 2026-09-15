export type VoiceboxProfile = {
  id: string;
  name: string;
};

export class VoiceboxError extends Error {}

function withTimeout(signal: AbortSignal | undefined, timeoutMs: number) {
  const timeout = AbortSignal.timeout(timeoutMs);
  return signal ? AbortSignal.any([signal, timeout]) : timeout;
}

export async function testVoiceboxConnection(
  baseUrl: string,
  signal?: AbortSignal,
): Promise<boolean> {
  try {
    const response = await fetch(`${baseUrl.replace(/\/+$/, "")}/health`, {
      signal: withTimeout(signal, 3_000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function listVoiceboxProfiles(
  baseUrl: string,
  signal?: AbortSignal,
): Promise<VoiceboxProfile[]> {
  const response = await fetch(`${baseUrl.replace(/\/+$/, "")}/profiles`, {
    signal: withTimeout(signal, 5_000),
  });
  if (!response.ok) throw new VoiceboxError(`Voicebox returned ${response.status}`);
  const body = await response.json();
  const profiles = Array.isArray(body) ? body : (body.profiles ?? []);
  return profiles.map((profile: { id: string; name?: string }) => ({
    id: profile.id,
    name: profile.name || profile.id,
  }));
}

export async function generateVoiceboxSpeech(
  baseUrl: string,
  profileId: string,
  text: string,
  signal?: AbortSignal,
): Promise<Blob> {
  const root = baseUrl.replace(/\/+$/, "");
  const generateResponse = await fetch(`${root}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: profileId, text, language: "en" }),
    signal: withTimeout(signal, 8_000),
  });
  if (!generateResponse.ok) {
    throw new VoiceboxError(`Voicebox generation failed (${generateResponse.status})`);
  }
  const generation = await generateResponse.json();
  const audioResponse = await fetch(`${root}/audio/${generation.id}`, {
    signal: withTimeout(signal, 8_000),
  });
  if (!audioResponse.ok) {
    throw new VoiceboxError(`Voicebox audio fetch failed (${audioResponse.status})`);
  }
  return audioResponse.blob();
}
