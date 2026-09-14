"use client";
import { useEffect, useRef, useState } from "react";
import type { RoadSignalApiClient, SessionSnapshot } from "../../lib/api-client";
import { assistantError, assistantRequest } from "../../lib/assistant";

type Status = { available: boolean; authorized_frames_allowed: boolean };
type Result = { model: string; counts: Record<string, number>; warnings: string[]; source: "demo" | "authorized" };

// Operate / inherited fleet surface. One explicit action processes one frame;
// estimates stay outside the live map, incident publication and safety scoring.
export function TrafficFrameCheck({ client, session }: { client: RoadSignalApiClient; session: SessionSnapshot | null }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [permission, setPermission] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef<AbortController | null>(null);
  const signedIn = !!session?.accessToken;
  useEffect(() => {
    pending.current?.abort(); setStatus(null); setResult(null); setFile(null); setPermission(false); setBusy(false); setError(null);
    return () => pending.current?.abort();
  }, [session?.user.id]);
  async function checkStatus() {
    if (!signedIn) return;
    const controller = new AbortController(); pending.current?.abort(); pending.current = controller;
    try { setStatus(await assistantRequest<Status>(client, "/api/v1/monitoring/vision/status", { signal: controller.signal }, 10_000)); }
    catch (cause) { if (!controller.signal.aborted) setError(assistantError(cause)); }
  }
  async function analyse(demo: boolean) {
    if (!signedIn || busy || (!demo && (!file || !permission || !status?.authorized_frames_allowed))) return;
    const controller = new AbortController(); pending.current?.abort(); pending.current = controller;
    setBusy(true); setError(null); setResult(null);
    try {
      let dataUrl: string;
      if (demo) {
        const canvas = document.createElement("canvas"); canvas.width = 320; canvas.height = 180;
        const context = canvas.getContext("2d");
        if (!context) throw new Error("This browser cannot create the demo test frame.");
        context.fillStyle = "#e8ece8"; context.fillRect(0, 0, canvas.width, canvas.height);
        dataUrl = canvas.toDataURL("image/png");
      } else {
        if (!file || !["image/png", "image/jpeg"].includes(file.type) || file.size > 512 * 1024) {
          throw new Error("Choose a PNG or JPEG no larger than 512 KiB.");
        }
        dataUrl = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader(); reader.onload = () => resolve(String(reader.result));
          reader.onerror = () => reject(new Error("The image could not be read.")); reader.readAsDataURL(file);
        });
      }
      if (controller.signal.aborted) return;
      const answer = await assistantRequest<Result>(client, "/api/v1/monitoring/vision/frames", {
        method: "POST", signal: controller.signal, body: JSON.stringify({ session_id: crypto.randomUUID(), frame_index: 0,
          image_base64: dataUrl.split(",")[1], source: demo ? "demo" : "authorized", authorization_confirmed: !demo && permission }),
      }, 100_000);
      if (!answer.counts || !Object.values(answer.counts).every((count) => Number.isInteger(count) && count >= 0)) {
        throw new Error("The model returned an invalid count result. No estimate is displayed.");
      }
      if (!controller.signal.aborted) setResult(answer);
    } catch (cause) { if (!controller.signal.aborted) setError(assistantError(cause)); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  return <details className="traffic-frame-check" onToggle={(event) => { if (event.currentTarget.open && !status) void checkStatus(); }}>
    <summary>Traffic frame check</summary>
    <p>RT-DETR detects vehicle boxes; ByteTrack associates them across frames. Counts here are estimates for one image, not traffic flow, speed or incident verification.</p>
    {!signedIn ? <p>Sign in to test the local model. No camera feed is connected.</p> : <>
      <p>{status ? status.available ? "Local vision worker is ready." : "Vision worker is unavailable. Start the model Docker profile, then recheck." : "Checking the local worker…"}</p>
      <div className="review-actions"><button type="button" disabled={busy || !status?.available} onClick={() => void analyse(true)}>Run blank demo frame</button>
        <button type="button" disabled={busy} onClick={() => void checkStatus()}>Recheck worker</button></div>
      <p className="automation-notice">The blank synthetic test contains no vehicles. It checks execution, not real-world accuracy.</p>
      {status?.authorized_frames_allowed && <div className="traffic-upload">
        <label>Optional authorized frame<input type="file" accept="image/png,image/jpeg" disabled={busy} onChange={(event) => { setFile(event.target.files?.[0] ?? null); setPermission(false); setResult(null); }} /></label>
        <label className="traffic-consent"><input type="checkbox" checked={permission} disabled={busy} onChange={(event) => setPermission(event.target.checked)} />I have permission to process this image.</label>
        <p>PNG/JPEG, at most 512 KiB and 2,073,600 pixels. Uploaded images are not retained by this analysis service.</p>
        <button type="button" disabled={busy || !file || !permission || !status.available} onClick={() => void analyse(false)}>Analyse selected frame</button>
      </div>}
      {busy && <p role="status">Analysing one frame on the local CPU…</p>}
      {error && <p role="alert" className="automation-error">{error}</p>}
      {result && <div className="frame-result" role="status"><h4>{result.source === "demo" ? "Synthetic frame result" : "Uploaded frame estimates"}</h4>
        <dl>{Object.entries(result.counts).map(([kind, count]) => <div key={kind}><dt>{kind}</dt><dd>{count}</dd></div>)}</dl>
        <p>No incident was verified or published. Nothing was added to route-risk scores.</p></div>}
    </>}
  </details>;
}
