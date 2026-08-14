import { create } from "zustand";
import { SafeRouteApiClient, type SessionSnapshot } from "./api-client";

export const API_URL =
  process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export const apiClient = new SafeRouteApiClient(API_URL);

type SessionStore = {
  session: SessionSnapshot | null;
  setSession: (session: SessionSnapshot | null) => void;
};

export const useSessionStore = create<SessionStore>((set) => ({
  session: null,
  setSession: (session) => set({ session }),
}));
