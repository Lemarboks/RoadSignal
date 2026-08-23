import * as Location from "expo-location";
import * as SecureStore from "expo-secure-store";
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { apiClient } from "../lib/session-store";

const PENDING_EMERGENCY_KEY = "roadsignal.mobile.pending-emergency.v1";
type Emergency = { id: string; status: string };

export default function Sos() {
  const [event, setEvent] = useState<Emergency | null>(null);
  const [state, setState] = useState<"idle" | "locating" | "syncing" | "synced" | "offline" | "cancelling">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  async function trigger() {
    setState("locating");
    let location = { latitude: -33.9249, longitude: 18.4241 };
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (permission.status === Location.PermissionStatus.GRANTED) {
        const current = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
        location = { latitude: current.coords.latitude, longitude: current.coords.longitude };
      }
    } catch {
      // The clearly labelled demonstration coordinate remains available.
    }

    const pending = { location, createdAt: new Date().toISOString(), simulation: true };
    await SecureStore.setItemAsync(PENDING_EMERGENCY_KEY, JSON.stringify(pending));
    setState("syncing");
    try {
      const created = await apiClient.request<Emergency>("/api/v1/emergencies", {
        method: "POST",
        body: JSON.stringify({ location }),
      });
      await SecureStore.deleteItemAsync(PENDING_EMERGENCY_KEY);
      setEvent(created);
      setState("synced");
    } catch {
      setState("offline");
    }
  }

  async function cancel() {
    if (!event) {
      await SecureStore.deleteItemAsync(PENDING_EMERGENCY_KEY);
      setState("idle");
      return;
    }
    setState("cancelling");
    try {
      await apiClient.request(`/api/v1/emergencies/${event.id}/cancel`, { method: "POST" });
      setEvent(null);
      setState("idle");
    } catch {
      setState("synced");
    }
  }

  const active = state !== "idle";
  return (
    <View style={s.page}>
      <Text style={s.mvp}>MVP SIMULATION — DOES NOT CALL EMERGENCY SERVICES</Text>
      <Text style={s.title}>Emergency SOS</Text>
      <Text style={s.description}>Hold for two seconds to share your current location with the demonstration fleet dashboard.</Text>
      <Pressable
        accessibilityHint="Hold for two seconds to create a simulated emergency event"
        accessibilityRole="button"
        disabled={active}
        style={({ pressed }) => [s.hold, pressed && s.holdPressed, active && s.holdActive]}
        onPressIn={() => { timer.current = setTimeout(() => void trigger(), 2000); }}
        onPressOut={() => { if (timer.current) clearTimeout(timer.current); timer.current = null; }}
      >
        {state === "locating" || state === "syncing" ? <ActivityIndicator color="white" /> : <Text style={s.white}>{active ? "SOS event active" : "Press and hold for 2 seconds"}</Text>}
      </Pressable>
      <Text accessibilityLiveRegion="polite" style={s.sync}>
        {state === "locating" && "Confirming the best available location…"}
        {state === "syncing" && "Recording the simulated emergency event…"}
        {state === "synced" && "Recorded on the demonstration fleet dashboard."}
        {state === "offline" && "Dashboard unavailable. The simulated event is secured on this device."}
        {state === "cancelling" && "Cancelling the simulated event…"}
      </Text>
      {active && state !== "locating" && state !== "syncing" && (
        <Pressable accessibilityRole="button" style={s.cancel} onPress={() => void cancel()}>
          <Text style={s.cancelText}>{state === "offline" ? "Clear on-device event" : "Cancel SOS event"}</Text>
        </Pressable>
      )}
      <Text style={s.contacts}>Emergency contacts{"\n"}Fleet control · +27 •• ••• ••••{"\n"}Sam Morgan · +27 •• ••• ••••</Text>
    </View>
  );
}

const s = StyleSheet.create({
  page: { flex: 1, padding: 25, justifyContent: "center", backgroundColor: "#fff" },
  mvp: { color: "#9f2222", fontWeight: "800" },
  title: { fontSize: 36, fontWeight: "800", marginTop: 16, marginBottom: 8 },
  description: { color: "#4f5e66", lineHeight: 21 },
  hold: { height: 160, borderRadius: 80, backgroundColor: "#b92f2f", alignItems: "center", justifyContent: "center", marginTop: 30 },
  holdPressed: { transform: [{ scale: 0.98 }] },
  holdActive: { backgroundColor: "#861f1f" },
  white: { color: "white", fontWeight: "800" },
  sync: { minHeight: 44, paddingTop: 12, fontSize: 12, lineHeight: 18, color: "#566871", textAlign: "center" },
  cancel: { minHeight: 48, alignItems: "center", justifyContent: "center", borderRadius: 12, borderWidth: 1, borderColor: "#b92f2f" },
  cancelText: { color: "#9f2222", fontWeight: "800" },
  contacts: { lineHeight: 27, backgroundColor: "#f5f7f8", padding: 18, marginTop: 24, borderRadius: 14 },
});
