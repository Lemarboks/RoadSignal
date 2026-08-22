"use client";

import { AuthPanel } from "./auth-panel";
import { RoadSignalApiClient, type SessionSnapshot } from "../lib/api-client";
import styles from "./entry-gate.module.css";

const STARTUP_VIDEO =
  "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260620_185230_f7f71ef4-6655-469f-b9c6-efbdc1f7684a.mp4";

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
    <div className={`${styles.gate} entry-gate`}>
      <video
        aria-hidden="true"
        autoPlay
        className={styles.video}
        loop
        muted
        playsInline
        preload="metadata"
      >
        <source src={STARTUP_VIDEO} type="video/mp4" />
      </video>
      <div className={styles.scrim} aria-hidden="true" />

      <div className={styles.layout}>
        <div className={styles.intro}>
          <div className={styles.brand}>
            <b>SR</b>
            <span>RoadSignal</span>
          </div>
          <p className={styles.kicker}>SAFER MOVEMENT STARTS HERE</p>
          <h1>
            <span>Beyond</span>
            <strong>risk.</strong>
            <span>Onward.</span>
          </h1>
        </div>

        <div className={`${styles.card} entry-gate-card`}>
          <h2>Welcome back</h2>
          <p className={styles.cardIntro}>
            Sign in to plan safer routes and receive live trip alerts.
          </p>
          <AuthPanel
            client={client}
            session={null}
            onSession={(session) => {
              if (session) onSession(session);
            }}
          />
          <div className={`${styles.divider} entry-gate-divider`}>
            <span>or</span>
          </div>
          <button
            className={`${styles.guest} entry-gate-guest`}
            type="button"
            onClick={onGuest}
          >
            Continue as guest &mdash; view demo
          </button>
          <p className={styles.note}>
            Demonstration risk estimates support decisions; they do not
            guarantee safety.
          </p>
        </div>
      </div>
    </div>
  );
}
