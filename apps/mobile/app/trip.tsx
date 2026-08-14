import { Link, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { apiClient } from "../lib/session-store";

type ApiRoute = { name: string; duration_minutes: number; safety_score: number };

function RouteTrack({ progress }: { progress: number }) {
  const clamped = Math.max(0, Math.min(progress, 100));
  return (
    <View style={s.map}>
      <View style={s.mapBadge}>
        <Text style={s.mapBadgeText}>Cape Town · simulated route</Text>
      </View>
      <View style={s.road}>
        <View style={[s.progressFill, { width: `${clamped}%` }]} />
        <View style={s.startMarker} />
        <View style={s.endMarker} />
        <View
          style={[
            s.vehicleMarker,
            { left: `${clamped}%`, marginLeft: -9 - (clamped / 100) * 4 },
          ]}
        />
      </View>
      <Text style={s.mapCaption}>{clamped}% of the way there</Text>
    </View>
  );
}

export default function Trip() {
  const params = useLocalSearchParams<{
    name?: string;
    durationMinutes?: string;
    safetyScore?: string;
    live?: string;
    origin?: string;
    destination?: string;
  }>();
  const origin = params.origin ?? "Cape Town City Centre";
  const destination = params.destination ?? "Cape Town International Airport";
  const [name, setName] = useState(params.name ?? "Airport route");
  const [duration, setDuration] = useState(
    params.durationMinutes ? Number(params.durationMinutes) : 26,
  );
  const [score, setScore] = useState(
    params.safetyScore ? Number(params.safetyScore) : 87,
  );
  const [progress, setProgress] = useState(12);
  const [rerouting, setRerouting] = useState(false);
  const [rerouteNotice, setRerouteNotice] = useState("");
  const isLive = params.live === "1";

  async function requestSaferReroute() {
    setRerouting(true);
    setRerouteNotice("");
    try {
      const data = await apiClient.request<{ routes: ApiRoute[] }>(
        "/api/v1/routes/analyse",
        {
          method: "POST",
          body: JSON.stringify({
            origin,
            destination,
            preference: "safest",
            departure_time: new Date().toISOString(),
            vehicle_type: "car",
          }),
        },
      );
      const safest = data.routes[0];
      if (safest) {
        setName(safest.name);
        setDuration(safest.duration_minutes);
        setScore(Math.round(safest.safety_score));
        setRerouteNotice("Switched to the safest available route.");
      } else {
        setRerouteNotice("No safer alternative route is available right now.");
      }
    } catch {
      setRerouteNotice("Could not reach the routing service. Continuing on the current route.");
    } finally {
      setRerouting(false);
    }
  }

  return (
    <View style={s.page}>
      <RouteTrack progress={progress} />
      <Text style={s.title}>
        {name} · {duration} min
      </Text>
      <Text style={s.score}>{score}/100 safety</Text>
      {isLive && <Text style={s.liveBadge}>Live route from the SafeRoute API</Text>}
      <Text style={s.next}>Next: Continue on Nelson Mandela Boulevard</Text>
      <Text style={s.alert}>Upcoming risk: Moderate congestion in 2.4 km</Text>
      <Pressable
        style={s.button}
        onPress={() => setProgress(Math.min(100, progress + 10))}
      >
        <Text style={s.white}>Advance simulation · {progress}%</Text>
      </Pressable>
      <Pressable style={s.outline} onPress={() => void requestSaferReroute()} disabled={rerouting}>
        {rerouting ? <ActivityIndicator /> : <Text style={s.outlineText}>Request safer reroute</Text>}
      </Pressable>
      {rerouteNotice ? <Text style={s.rerouteNotice}>{rerouteNotice}</Text> : null}
      <Link href="/sos" style={s.sosLink} asChild>
        <Pressable style={s.sos}>
          <Text style={s.white}>SOS</Text>
        </Pressable>
      </Link>
    </View>
  );
}

const s = StyleSheet.create({
  page: { flex: 1, padding: 22, backgroundColor: "#f5f7f8" },
  map: {
    height: 220,
    backgroundColor: "#e3edea",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 16,
    overflow: "hidden",
  },
  mapBadge: {
    position: "absolute",
    top: 12,
    left: 12,
    backgroundColor: "rgba(255,255,255,.92)",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  mapBadgeText: { fontSize: 11, fontWeight: "700", color: "#14212b" },
  road: {
    width: "78%",
    height: 8,
    borderRadius: 999,
    backgroundColor: "#c7d6d1",
    position: "relative",
    marginTop: 10,
  },
  progressFill: {
    position: "absolute",
    top: 0,
    left: 0,
    bottom: 0,
    backgroundColor: "#1769aa",
    borderRadius: 999,
  },
  startMarker: {
    position: "absolute",
    left: -5,
    top: -4,
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: "#178652",
    borderWidth: 2,
    borderColor: "white",
  },
  endMarker: {
    position: "absolute",
    right: -5,
    top: -4,
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: "#c33d3d",
    borderWidth: 2,
    borderColor: "white",
  },
  vehicleMarker: {
    position: "absolute",
    top: -9,
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: "#1769aa",
    borderWidth: 3,
    borderColor: "white",
    shadowColor: "#000",
    shadowOpacity: 0.25,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 2 },
    elevation: 3,
  },
  mapCaption: { marginTop: 24, fontSize: 12, color: "#4a5c56" },
  title: { fontSize: 25, fontWeight: "700", marginTop: 20 },
  score: { fontSize: 30, fontWeight: "800", color: "#178652" },
  liveBadge: { fontSize: 12, fontWeight: "700", color: "#178652", marginBottom: 6 },
  next: { marginTop: 6 },
  alert: { backgroundColor: "#fff3d9", padding: 15, marginVertical: 18, borderRadius: 9 },
  button: { backgroundColor: "#1769aa", padding: 15, alignItems: "center", borderRadius: 10 },
  outline: {
    borderWidth: 1,
    borderColor: "#1769aa",
    padding: 15,
    alignItems: "center",
    marginTop: 10,
    borderRadius: 10,
  },
  outlineText: { color: "#1769aa", fontWeight: "700" },
  rerouteNotice: { marginTop: 8, fontSize: 12, color: "#4a5c56", textAlign: "center" },
  sosLink: { marginTop: 10 },
  sos: { backgroundColor: "#c33d3d", padding: 15, alignItems: "center", borderRadius: 10 },
  white: { color: "white", fontWeight: "700" },
});
