import { Link, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { apiClient } from "../lib/session-store";

type ApiRoute = { name: string; duration_minutes: number; safety_score: number };

export default function Trip() {
  const params = useLocalSearchParams<{
    name?: string;
    durationMinutes?: string;
    safetyScore?: string;
    live?: string;
  }>();
  const [name, setName] = useState(params.name ?? "Airport route");
  const [duration, setDuration] = useState(
    params.durationMinutes ? Number(params.durationMinutes) : 26,
  );
  const [score, setScore] = useState(
    params.safetyScore ? Number(params.safetyScore) : 87,
  );
  const [progress, setProgress] = useState(12);
  const [rerouting, setRerouting] = useState(false);
  const isLive = params.live === "1";

  async function requestSaferReroute() {
    setRerouting(true);
    try {
      const data = await apiClient.request<{ routes: ApiRoute[] }>(
        "/api/v1/routes/analyse",
        {
          method: "POST",
          body: JSON.stringify({
            origin: "Cape Town City Centre",
            destination: "Cape Town International Airport",
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
      }
    } catch {
      // The trip continues on the current route if a reroute can't be fetched.
    } finally {
      setRerouting(false);
    }
  }

  return (
    <View style={s.page}>
      <View style={s.map}>
        <Text>Simulated Cape Town route map</Text>
        <Text style={s.pin}>● ━━━━━━━ ◉</Text>
      </View>
      <Text style={s.title}>
        {name} · {duration} min
      </Text>
      <Text style={s.score}>{score}/100 safety</Text>
      {isLive && <Text style={s.liveBadge}>Live route from the SafeRoute API</Text>}
      <Text>Next: Continue on Nelson Mandela Boulevard</Text>
      <Text style={s.alert}>Upcoming risk: Moderate congestion in 2.4 km</Text>
      <Pressable
        style={s.button}
        onPress={() => setProgress(Math.min(100, progress + 10))}
      >
        <Text style={s.white}>Advance simulation · {progress}%</Text>
      </Pressable>
      <Pressable style={s.outline} onPress={() => void requestSaferReroute()} disabled={rerouting}>
        {rerouting ? <ActivityIndicator /> : <Text>Request safer reroute</Text>}
      </Pressable>
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
    height: 300,
    backgroundColor: "#dfe9e7",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 10,
  },
  pin: { fontSize: 32, color: "#1769aa", marginTop: 30 },
  title: { fontSize: 25, fontWeight: "700", marginTop: 20 },
  score: { fontSize: 30, fontWeight: "800", color: "#178652" },
  liveBadge: { fontSize: 12, fontWeight: "700", color: "#178652", marginBottom: 6 },
  alert: { backgroundColor: "#fff3d9", padding: 15, marginVertical: 18 },
  button: { backgroundColor: "#1769aa", padding: 15, alignItems: "center", borderRadius: 7 },
  outline: {
    borderWidth: 1,
    borderColor: "#1769aa",
    padding: 15,
    alignItems: "center",
    marginTop: 10,
    borderRadius: 7,
  },
  sosLink: { marginTop: 10 },
  sos: { backgroundColor: "#c33d3d", padding: 15, alignItems: "center", borderRadius: 7 },
  white: { color: "white", fontWeight: "700" },
});
