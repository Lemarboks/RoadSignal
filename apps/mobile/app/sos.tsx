import { useRef, useState } from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { apiClient } from "../lib/session-store";

export default function Sos() {
  const [armed, setArmed] = useState(false);
  const [synced, setSynced] = useState<"idle" | "syncing" | "synced" | "failed">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function trigger() {
    setArmed(true);
    setSynced("syncing");
    apiClient
      .request("/api/v1/incidents", {
        method: "POST",
        body: JSON.stringify({
          incident_type: "SOS",
          severity: 5,
          description: "Simulated SOS event from the mobile demonstration app.",
          location: { latitude: -33.9249, longitude: 18.4241 },
        }),
      })
      .then(() => setSynced("synced"))
      .catch(() => setSynced("failed"));
  }

  return (
    <View style={s.page}>
      <Text style={s.mvp}>MVP SIMULATION — DOES NOT CALL EMERGENCY SERVICES</Text>
      <Text style={s.title}>Emergency SOS</Text>
      <Text>
        Your simulated current location and emergency event will be shared with the
        demonstration fleet dashboard.
      </Text>
      <Pressable
        style={s.hold}
        onPressIn={() => {
          timer.current = setTimeout(trigger, 2000);
        }}
        onPressOut={() => {
          if (timer.current) clearTimeout(timer.current);
        }}
      >
        <Text style={s.white}>
          {armed ? "SOS event created · Cancel" : "Press and hold for 2 seconds"}
        </Text>
      </Pressable>
      {armed && (
        <Text style={s.sync}>
          {synced === "syncing" && "Recording event on the demonstration fleet dashboard…"}
          {synced === "synced" && "Recorded on the demonstration fleet dashboard."}
          {synced === "failed" && "Could not reach the demonstration fleet dashboard; event stayed on-device only."}
        </Text>
      )}
      <Text style={s.contacts}>
        Emergency contacts{"\n"}
        Fleet control · +27 •• ••• ••••{"\n"}
        Sam Morgan · +27 •• ••• ••••
      </Text>
    </View>
  );
}

const s = StyleSheet.create({
  page: { flex: 1, padding: 25, justifyContent: "center", backgroundColor: "#fff" },
  mvp: { color: "#c33d3d", fontWeight: "800" },
  title: { fontSize: 36, fontWeight: "800", marginVertical: 18 },
  hold: {
    height: 160,
    borderRadius: 80,
    backgroundColor: "#c33d3d",
    alignItems: "center",
    justifyContent: "center",
    marginVertical: 35,
  },
  white: { color: "white", fontWeight: "800" },
  sync: { fontSize: 12, color: "#66737d", textAlign: "center", marginBottom: 20 },
  contacts: { lineHeight: 27, backgroundColor: "#f5f7f8", padding: 18 },
});
