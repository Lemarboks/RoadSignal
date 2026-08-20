"use client";

import { AuthPanel } from "./auth-panel";
import { RoadSignalApiClient, type SessionSnapshot } from "../lib/api-client";

export function EntryGate({
  client,
  onSession,
  onGuest,
}: {
  client: RoadSignalApiClient;
  onSession: (session: SessionSnapshot) => void;
  onGuest: () => void;
}) {
  return (
    <div className="entry-gate">
      <div className="entry-gate-card">
        <div className="entry-gate-brand">
          <b>SR</b>
          <span>
            RoadSignal <strong>AI</strong>
          </span>
        </div>
        <h1>Route-risk intelligence for Cape Town</h1>
        <p>
          Sign in for protected trips, incident reporting, and realtime alerts
          &mdash; or continue without an account to explore the showcase with
          public and demonstration data.
        </p>
        <AuthPanel
          client={client}
          session={null}
          onSession={(session) => {
            if (session) onSession(session);
          }}
        />
        <div className="entry-gate-divider">
          <span>or</span>
        </div>
        <button className="entry-gate-guest" type="button" onClick={onGuest}>
          Continue as guest &mdash; view demo
        </button>
        <p className="entry-gate-note">
          All included people, trips, incidents, and scores are demonstration
          data. It is decision support, not a guarantee of safety.
        </p>
      </div>
    </div>
  );
}
