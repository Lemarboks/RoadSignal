"use client";

import { FormEvent, useState } from "react";
import { ApiError, SafeRouteApiClient, type SessionSnapshot } from "../lib/api-client";

export function AuthPanel({
  client,
  session,
  onSession,
}: {
  client: SafeRouteApiClient;
  session: SessionSnapshot | null;
  onSession: (session: SessionSnapshot | null) => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (session) {
    return (
      <section className="session-panel" aria-label="Signed-in account">
        <span className="session-avatar" aria-hidden="true">
          {session.user.name.slice(0, 2).toUpperCase()}
        </span>
        <span className="session-identity">
          <strong>{session.user.name}</strong>
          <small>{session.user.role.replaceAll("_", " ")}</small>
        </span>
        <button
          type="button"
          onClick={() => {
            void client.logout();
            onSession(null);
          }}
        >
          Sign out
        </button>
      </section>
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const email = String(data.get("email") ?? "");
      const password = String(data.get("password") ?? "");
      const next =
        mode === "register"
          ? await client.register(String(data.get("name") ?? ""), email, password)
          : await client.login(email, password);
      onSession(next);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "The API could not be reached. Check the connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="auth-panel" aria-labelledby="auth-title">
      <div>
        <h2 id="auth-title">{mode === "login" ? "Connect your account" : "Create a driver account"}</h2>
        <p>Sign in to use protected trips, incident reporting, and realtime alerts.</p>
      </div>
      <form onSubmit={submit} aria-describedby={error ? "auth-error" : undefined}>
        {mode === "register" && (
          <label>
            Name
            <input name="name" autoComplete="name" minLength={2} maxLength={100} required />
          </label>
        )}
        <label>
          Email
          <input name="email" type="email" autoComplete="email" maxLength={255} required />
        </label>
        <label>
          Password
          <input
            name="password"
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            minLength={12}
            maxLength={128}
            aria-describedby={mode === "register" ? "password-hint" : undefined}
            required
          />
        </label>
        {mode === "register" && <small id="password-hint">Use at least 12 characters and avoid common passwords.</small>}
        {error && <p className="auth-error" id="auth-error" role="alert">{error}</p>}
        <button className="primary" type="submit" disabled={busy}>
          {busy ? "Connecting..." : mode === "login" ? "Sign in securely" : "Create account"}
        </button>
      </form>
      <button
        className="auth-switch"
        type="button"
        onClick={() => {
          setError("");
          setMode((current) => (current === "login" ? "register" : "login"));
        }}
      >
        {mode === "login" ? "Need an account? Register" : "Already registered? Sign in"}
      </button>
      <small className="session-note">Tokens stay in memory and are cleared when this tab reloads or closes.</small>
    </section>
  );
}
