import * as SecureStore from "expo-secure-store";
import { create } from "zustand";
import {
  RoadSignalApiClient,
  type PersistedSession,
  type SessionSnapshot,
  type SessionUser,
} from "./api-client";

export const API_URL =
  process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export const apiClient = new RoadSignalApiClient(API_URL);

const SESSION_KEY = "roadsignal.mobile.refresh-session.v1";

function isPersistedSession(value: unknown): value is PersistedSession {
  if (!value || typeof value !== "object") return false;
  const candidate = value as { refreshToken?: unknown; user?: Partial<SessionUser> };
  const roles: SessionUser["role"][] = [
    "driver",
    "fleet_manager",
    "incident_moderator",
    "administrator",
  ];
  return (
    typeof candidate.refreshToken === "string" &&
    candidate.refreshToken.length >= 40 &&
    typeof candidate.user?.id === "string" &&
    typeof candidate.user.email === "string" &&
    typeof candidate.user.name === "string" &&
    roles.includes(candidate.user.role as SessionUser["role"])
  );
}

export async function restorePersistedSession() {
  const stored = await SecureStore.getItemAsync(SESSION_KEY);
  if (!stored) return null;
  const parsed: unknown = JSON.parse(stored);
  if (!isPersistedSession(parsed)) {
    await SecureStore.deleteItemAsync(SESSION_KEY);
    return null;
  }
  return apiClient.restore(parsed);
}

apiClient.setPersistenceListener((session) => {
  const operation = session
    ? SecureStore.setItemAsync(SESSION_KEY, JSON.stringify(session))
    : SecureStore.deleteItemAsync(SESSION_KEY);
  void operation.catch(() => {
    // Authentication still works in memory if encrypted storage is unavailable.
  });
});

type SessionStore = {
  session: SessionSnapshot | null;
  hydrated: boolean;
  hydrate: () => Promise<void>;
  setSession: (session: SessionSnapshot | null) => void;
};

export const useSessionStore = create<SessionStore>((set) => ({
  session: null,
  hydrated: false,
  hydrate: async () => {
    try {
      const session = await restorePersistedSession();
      set({ session });
    } catch {
      await SecureStore.deleteItemAsync(SESSION_KEY).catch(() => undefined);
    } finally {
      set({ hydrated: true });
    }
  },
  setSession: (session) => set({ session }),
}));
