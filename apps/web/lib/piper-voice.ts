/**
 * Server-side neural speech via the API's Piper endpoint.
 *
 * Unlike the Voicebox engine this needs no extra host, port or CORS setup from
 * the user: the audio comes from the same API the app already talks to.
 */
export type PiperStatus = {
  configured: boolean;
  available: boolean;
  voice_model: string;
  binary_found: boolean;
  model_found: boolean;
};

export async function fetchPiperStatus(apiUrl: string, signal?: AbortSignal): Promise<PiperStatus | null> {
  try {
    const response = await fetch(`${apiUrl}/api/v1/voice/status`, { signal });
    if (!response.ok) return null;
    const body = await response.json();
    return (body?.piper ?? null) as PiperStatus | null;
  } catch {
    return null;
  }
}

export async function generatePiperSpeech(
  apiUrl: string,
  text: string,
  signal?: AbortSignal,
): Promise<Blob> {
  const response = await fetch(`${apiUrl}/api/v1/voice/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
    signal,
  });
  if (!response.ok) {
    throw new Error(`Piper speech failed (${response.status})`);
  }
  const blob = await response.blob();
  if (!blob.size) throw new Error("Piper returned empty audio");
  return blob;
}
