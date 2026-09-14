import { useEffect, useRef, useState, type FormEvent } from "react";
import { PlaceSearch } from "../../components/place-search";
import type { RoadSignalApiClient } from "../../lib/api-client";
import { assistantError, assistantRequest, type AssistantStatus, type IncidentAnalysis, type IncidentReport } from "../../lib/assistant";
import type { ResolvedPlace } from "../../lib/open-routing";

export function IncidentComposer({ client, signedIn, serviceEnabled, status, initialPlace, onReport, onClose }: {
  client: RoadSignalApiClient;
  signedIn: boolean;
  serviceEnabled: boolean;
  status: AssistantStatus | null;
  initialPlace: ResolvedPlace | null;
  onReport: (report: IncidentReport) => Promise<void>;
  onClose: () => void;
}) {
  const [description, setDescription] = useState("");
  const [incidentType, setIncidentType] = useState("Road hazard");
  const [severity, setSeverity] = useState(2);
  const [place, setPlace] = useState(initialPlace);
  const [placeText, setPlaceText] = useState(initialPlace?.displayName ?? "");
  const [analysis, setAnalysis] = useState<IncidentAnalysis | null>(null);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [busy, setBusy] = useState<"analyse" | "transcribe" | "submit" | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [recording, setRecording] = useState(false);
  const [requestingMicrophone, setRequestingMicrophone] = useState(false);
  const request = useRef<AbortController | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const recordingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mounted = useRef(true);
  const canAssist = signedIn && serviceEnabled;
  const canTranscribe = canAssist && Boolean(status?.transcription.configured);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      request.current?.abort();
      if (recordingTimer.current) clearTimeout(recordingTimer.current);
      if (recorder.current?.state === "recording") recorder.current.stop();
      recorder.current?.stream.getTracks().forEach((track) => track.stop());
    };
  }, []);
  function beginRequest(action: "analyse" | "transcribe") {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy(action); setError(""); setMessage("");
    return controller;
  }
  async function analyse() {
    const controller = beginRequest("analyse");
    setAnalysis(null);
    try {
      const result = await assistantRequest<IncidentAnalysis>(client, "/api/v1/assistant/incidents/analyse", {
        method: "POST", signal: controller.signal,
        body: JSON.stringify({ text: description, ...(place ? { latitude: place.latitude, longitude: place.longitude } : {}) }),
      });
      if (!controller.signal.aborted) setAnalysis(result);
    } catch (failure) {
      if (!controller.signal.aborted) setError(assistantError(failure));
    } finally { if (!controller.signal.aborted) setBusy(null); }
  }
  async function transcribe(file: File) {
    if (file.size > 10 * 1024 * 1024) { setError("Choose an audio file of 10 MiB or less, up to 90 seconds long."); return; }
    const controller = beginRequest("transcribe");
    setTranscript(null);
    const body = new FormData(); body.append("file", file);
    try {
      const result = await assistantRequest<{ text: string }>(client, "/api/v1/assistant/transcribe", {
        method: "POST", body, signal: controller.signal,
      }, 90_000);
      if (!controller.signal.aborted) setTranscript(result.text);
    } catch (failure) {
      if (!controller.signal.aborted) setError(assistantError(failure));
    } finally { if (!controller.signal.aborted) setBusy(null); }
  }
  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("This browser cannot record audio. Upload an audio file instead."); return;
    }
    setError("");
    setRequestingMicrophone(true);
    let stream: MediaStream | null = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mounted.current) { stream.getTracks().forEach((track) => track.stop()); return; }
      const mediaRecorder = new MediaRecorder(stream);
      recorder.current = mediaRecorder;
      const chunks: BlobPart[] = [];
      mediaRecorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      mediaRecorder.onstop = () => {
        mediaRecorder.stream.getTracks().forEach((track) => track.stop());
        if (recordingTimer.current) clearTimeout(recordingTimer.current);
        if (!mounted.current) return;
        setRecording(false);
        const extension = mediaRecorder.mimeType.includes("mp4") ? "m4a" : "webm";
        void transcribe(new File(chunks, `incident.${extension}`, { type: mediaRecorder.mimeType }));
      };
      mediaRecorder.start(); setRecording(true);
      recordingTimer.current = setTimeout(() => {
        if (mediaRecorder.state === "recording") mediaRecorder.stop();
      }, 60_000);
    } catch {
      stream?.getTracks().forEach((track) => track.stop());
      setError("Microphone access was not available. Allow it in browser settings or upload an audio file.");
    } finally { if (mounted.current) setRequestingMicrophone(false); }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!place) { setError("Choose a location from the suggestions before submitting."); return; }
    setBusy("submit"); setError("");
    try {
      await onReport({ incident_type: incidentType, severity, description: description.trim(), location: { latitude: place.latitude, longitude: place.longitude } });
      onClose();
    } catch (failure) {
      if (mounted.current) { setError(assistantError(failure)); setBusy(null); }
    }
  }
  const locked = Boolean(busy) || recording || requestingMicrophone;
  return (
    <section className="panel incident-composer" aria-labelledby="incident-composer-title">
      <div className="composer-heading"><div><h2 id="incident-composer-title">Describe what happened</h2>
        <p>{signedIn && serviceEnabled ? "Review the details and location before submitting your report." : "This report will be saved in this demonstration session only."}</p>
      </div><button type="button" onClick={onClose} disabled={busy === "submit"}>Cancel</button></div>
      <form onSubmit={(event) => void submit(event)}>
        <label>Description<textarea autoFocus value={description} required minLength={5} maxLength={1000} rows={4}
          disabled={locked} placeholder="What happened, where, and which direction is affected?"
          onChange={(event) => { setDescription(event.target.value); setAnalysis(null); setMessage(""); }} /></label>
        <div className="assistant-actions">
          <button type="button" disabled={!canAssist || locked || description.trim().length < 5} onClick={() => void analyse()}>
            {busy === "analyse" ? "Checking report…" : "Help draft & check duplicates"}
          </button>
          <button type="button" disabled={!canTranscribe || Boolean(busy) || requestingMicrophone} onClick={() => recording ? recorder.current?.stop() : void startRecording()}>
            {recording ? "Stop & transcribe" : "Record voice report"}
          </button>
          <label className={`audio-upload ${!canTranscribe || locked ? "disabled" : ""}`}>Upload audio
            <input type="file" aria-label="Upload incident audio" accept="audio/*,.webm,.m4a,.mp3,.wav,.ogg" disabled={!canTranscribe || locked}
              onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) void transcribe(file); }} />
          </label>
        </div>
        <p className="assistant-caption" role="status">
          {recording ? "Recording, up to 60 seconds. Stop to create a transcript for review."
            : busy === "transcribe" ? "Transcribing audio… You will be able to correct it before use."
              : !canAssist ? "Sign in to use report assistance and voice input. Manual reporting is available."
                : !status ? "Assistant status unavailable. You can still enter a report manually."
                  : !status.transcription.configured ? "Text assistance available. Voice input is not configured on this service."
                    : !status.transcription.available ? "Voice service is loading or unavailable. You can still enter a report manually and retry voice later."
                    : "Voice recordings are sent to the configured transcription service. Review recognition carefully, especially place names."}
        </p>
        {transcript !== null && <section className="assistant-review" aria-label="Review voice transcript">
          <h3>Review transcript</h3><label>Correct the transcript<textarea value={transcript} rows={3} maxLength={1000}
            onChange={(event) => setTranscript(event.target.value)} /></label>
          <button type="button" disabled={locked || !transcript.trim()} onClick={() => { setDescription(transcript.slice(0, 1000)); setTranscript(null); setAnalysis(null); setMessage("Transcript applied. Check the report details before submitting."); }}>Use corrected transcript</button>
        </section>}
        {analysis && <section className="assistant-review" aria-label="Review suggested report">
          <h3>Review suggested details</h3>
          <p className="assistant-caption">{analysis.mode === "model" ? "AI-assisted draft" : "Rule-based draft"} · nothing has been submitted.</p>
          <p><strong>{analysis.draft.incident_type}</strong> · severity {analysis.draft.severity}/5</p><p>{analysis.draft.description}</p>
          <button type="button" disabled={locked} onClick={() => {
            setIncidentType(analysis.draft.incident_type); setSeverity(analysis.draft.severity); setDescription(analysis.draft.description);
            setAnalysis(null); setMessage("Suggested details applied. Review and edit them before submitting.");
          }}>Apply suggested details</button>
          {analysis.duplicates.length > 0 && <div className="duplicate-candidates"><h3>Possible existing reports</h3>
            <p className="assistant-caption">Review these before adding a report. Similarity is not confirmation of a duplicate.</p>
            <ul>{analysis.duplicates.map((item) => <li key={item.id}>
              <a href={`#incident-${encodeURIComponent(item.id)}`}>{item.incident_type}</a>
              <p>{item.description}</p><small>{item.distance_km === null ? "Distance unavailable" : `${item.distance_km.toFixed(1)} km away`} · reported {new Date(item.occurred_at).toLocaleString()}</small>
            </li>)}</ul>
          </div>}
          {analysis.duplicates.length === 0 && <p className="assistant-caption">No similar reports returned in the search area.</p>}
          {analysis.warnings.map((warning) => <p className="assistant-caption" key={warning}>{warning}</p>)}
        </section>}
        <div className="report-fields"><label>Incident type<input value={incidentType} onChange={(event) => setIncidentType(event.target.value)} minLength={2} maxLength={50} required disabled={locked} /></label>
          <label>Severity<select value={severity} onChange={(event) => setSeverity(Number(event.target.value))} disabled={locked}>
            <option value={1}>1 · Minor</option><option value={2}>2 · Moderate</option><option value={3}>3 · Significant</option><option value={4}>4 · Severe</option><option value={5}>5 · Critical</option>
          </select></label>
        </div>
        <fieldset className="report-location" disabled={locked}><label>Incident location<PlaceSearch value={placeText} resolved={place} onChange={(value) => { setPlaceText(value); setPlace(null); setAnalysis(null); }} onResolved={(value) => { setPlace(value); setAnalysis(null); }} placeholder="Street, landmark or suburb" /></label></fieldset>
        <p className="assistant-caption">Confirm the location matches the incident. It starts at your selected route origin.</p>
        {error && <p className="assistant-error" role="alert">{error}</p>}
        {message && <p className="assistant-caption" role="status">{message}</p>}
        <button type="submit" className="primary" disabled={locked || !place || description.trim().length < 5}>
          {busy === "submit" ? "Submitting…" : signedIn && serviceEnabled ? "Submit reviewed report" : "Save demo report"}
        </button>
      </form>
    </section>
  );
}
