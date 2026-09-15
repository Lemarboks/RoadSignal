"use client";

import { useEffect, useState } from "react";
import {
  applyTheme,
  loadPreferences,
  savePreferences,
  type Preferences,
} from "../../lib/preferences";
import { listVoiceboxProfiles, testVoiceboxConnection, type VoiceboxProfile } from "../../lib/voicebox";

type VoiceboxStatus = "idle" | "checking" | "connected" | "unreachable";

export function SettingsPage() {
  const [preferences, setPreferences] = useState<Preferences>(() => loadPreferences());
  const [voiceboxStatus, setVoiceboxStatus] = useState<VoiceboxStatus>("idle");
  const [voiceboxProfiles, setVoiceboxProfiles] = useState<VoiceboxProfile[]>([]);

  function update(patch: Partial<Preferences>) {
    setPreferences((current) => {
      const next = { ...current, ...patch };
      savePreferences(next);
      return next;
    });
  }

  useEffect(() => {
    applyTheme(preferences.theme);
  }, [preferences.theme]);

  async function checkVoicebox() {
    setVoiceboxStatus("checking");
    const reachable = await testVoiceboxConnection(preferences.voiceboxUrl);
    if (!reachable) {
      setVoiceboxStatus("unreachable");
      setVoiceboxProfiles([]);
      return;
    }
    try {
      const profiles = await listVoiceboxProfiles(preferences.voiceboxUrl);
      setVoiceboxProfiles(profiles);
      setVoiceboxStatus("connected");
      if (!preferences.voiceboxProfileId && profiles[0]) {
        update({ voiceboxProfileId: profiles[0].id });
      }
    } catch {
      setVoiceboxStatus("unreachable");
      setVoiceboxProfiles([]);
    }
  }

  return (
    <>
      <section className="heading">
        <div>
          <p className="eyebrow">App preferences</p>
          <h1>Settings</h1>
          <p>Personalise how RoadSignal looks and sounds on this device.</p>
        </div>
      </section>
      <div className="settings-layout">
        <section className="panel settings-section" aria-labelledby="appearance-title">
          <h2 id="appearance-title">Appearance</h2>
          <label className="settings-field">
            <span>Theme</span>
            <select
              value={preferences.theme}
              onChange={(event) => update({ theme: event.target.value as Preferences["theme"] })}
            >
              <option value="system">Match system</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </label>
          <label className="settings-field">
            <span>Distance units</span>
            <select
              value={preferences.distanceUnit}
              onChange={(event) => update({ distanceUnit: event.target.value as Preferences["distanceUnit"] })}
            >
              <option value="km">Kilometres</option>
              <option value="mi">Miles</option>
            </select>
          </label>
        </section>
        <section className="panel settings-section" aria-labelledby="voice-title">
          <h2 id="voice-title">Voice guidance</h2>
          <label className="settings-toggle">
            <input
              type="checkbox"
              checked={preferences.voiceAlertsDefault}
              onChange={(event) => update({ voiceAlertsDefault: event.target.checked })}
            />
            <span>Announce trip hazards and turns by voice by default</span>
          </label>
          <label className="settings-field">
            <span>Voice engine</span>
            <select
              value={preferences.voiceEngine}
              onChange={(event) => update({ voiceEngine: event.target.value as Preferences["voiceEngine"] })}
            >
              <option value="browser">Browser voice (built-in)</option>
              <option value="voicebox">Voicebox (self-hosted neural voices)</option>
            </select>
          </label>
          {preferences.voiceEngine === "voicebox" && (
            <div className="voicebox-config">
              <label className="settings-field">
                <span>Voicebox server URL</span>
                <input
                  type="text"
                  value={preferences.voiceboxUrl}
                  onChange={(event) => update({ voiceboxUrl: event.target.value })}
                  placeholder="http://127.0.0.1:17493"
                />
              </label>
              <button
                type="button"
                onClick={() => void checkVoicebox()}
                disabled={voiceboxStatus === "checking"}
              >
                {voiceboxStatus === "checking" ? "Checking..." : "Test connection"}
              </button>
              {voiceboxStatus === "connected" && (
                <p className="settings-status ok" role="status">
                  Connected. {voiceboxProfiles.length} voice profile{voiceboxProfiles.length === 1 ? "" : "s"} available.
                </p>
              )}
              {voiceboxStatus === "unreachable" && (
                <p className="settings-status error" role="status">
                  Couldn&rsquo;t reach Voicebox at this URL. Voice guidance will use the browser voice instead.
                </p>
              )}
              {voiceboxProfiles.length > 0 && (
                <label className="settings-field">
                  <span>Voice profile</span>
                  <select
                    value={preferences.voiceboxProfileId}
                    onChange={(event) => update({ voiceboxProfileId: event.target.value })}
                  >
                    {voiceboxProfiles.map((profile) => (
                      <option key={profile.id} value={profile.id}>
                        {profile.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <p className="settings-note">
                Requires{" "}
                <a href="https://github.com/jamiepine/voicebox" target="_blank" rel="noreferrer">
                  Voicebox
                </a>{" "}
                running locally or self-hosted, with this origin allowed via{" "}
                <code>VOICEBOX_CORS_ORIGINS</code>. Falls back to the browser voice automatically if
                unreachable or a profile isn&rsquo;t selected.
              </p>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
