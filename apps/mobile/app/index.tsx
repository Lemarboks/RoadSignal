import * as Location from "expo-location";
import { Link, router } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { apiClient, useSessionStore } from "../lib/session-store";

type PermissionState = "unknown" | "requesting" | "granted" | "denied";

type ApiRoute = {
  id: string;
  name: string;
  duration_minutes: number;
  safety_score: number;
};

export default function Home() {
  const session = useSessionStore((state) => state.session);
  const setSession = useSessionStore((state) => state.setSession);
  const [permission, setPermission] = useState<PermissionState>("unknown");
  const [locationLabel, setLocationLabel] = useState(
    "Cape Town CBD · simulation",
  );
  const [origin, setOrigin] = useState("Cape Town City Centre");
  const [destination, setDestination] = useState("Cape Town International Airport");
  const [searching, setSearching] = useState(false);
  const [notice, setNotice] = useState("");

  async function enableLocation() {
    setPermission("requesting");
    const result = await Location.requestForegroundPermissionsAsync();
    if (result.status !== Location.PermissionStatus.GRANTED) {
      setPermission("denied");
      return;
    }
    const current = await Location.getCurrentPositionAsync({
      accuracy: Location.Accuracy.Balanced,
    });
    setLocationLabel(
      `${current.coords.latitude.toFixed(5)}, ${current.coords.longitude.toFixed(5)}`,
    );
    setPermission("granted");
  }

  async function startSafeRoute() {
    setSearching(true);
    setNotice("");
    try {
      const data = await apiClient.request<{ routes: ApiRoute[]; provider?: string }>(
        "/api/v1/routes/analyse",
        {
          method: "POST",
          body: JSON.stringify({
            origin,
            destination,
            preference: "balanced",
            departure_time: new Date().toISOString(),
            vehicle_type: "car",
          }),
        },
      );
      const best = data.routes.find((r) => r.name) ?? data.routes[0];
      router.push({
        pathname: "/trip",
        params: {
          name: best.name,
          durationMinutes: String(best.duration_minutes),
          safetyScore: String(Math.round(best.safety_score)),
          live: data.provider === "open" ? "1" : "0",
          origin,
          destination,
        },
      });
    } catch {
      setNotice("Live routing is unavailable. Continuing with the simulated demo trip.");
      router.push("/trip");
    } finally {
      setSearching(false);
    }
  }

  return (
    <SafeAreaView style={styles.page}>
      <View style={styles.authRow}>
        <Text style={styles.authText}>
          {session ? `Signed in as ${session.user.name}` : "Not signed in"}
        </Text>
        {session ? (
          <Pressable onPress={() => void apiClient.logout().then(() => setSession(null))}>
            <Text style={styles.authLink}>Sign out</Text>
          </Pressable>
        ) : (
          <Link href="/login" style={styles.authLink}>
            Sign in
          </Link>
        )}
      </View>
      <Text style={styles.eyebrow}>CAPE TOWN · DEMONSTRATION MODE</Text>
      <Text style={styles.title}>You are in a low-risk area</Text>
      <View style={styles.score}>
        <Text style={styles.scoreNumber}>88</Text>
        <Text>/100 current safety estimate</Text>
      </View>

      <View style={styles.permissionCard}>
        <View style={styles.permissionCopy}>
          <Text style={styles.permissionTitle}>
            {permission === "granted"
              ? "Location enabled"
              : permission === "denied"
                ? "Location permission denied"
                : "Enable current location"}
          </Text>
          <Text style={styles.permissionText}>
            {permission === "granted"
              ? "Your position can now be used for route planning."
              : permission === "denied"
                ? "Enable permission in device settings, or continue in simulation mode."
                : "Requested only when you press Enable. Simulation remains available."}
          </Text>
        </View>
        {permission !== "granted" && (
          <Pressable
            accessibilityRole="button"
            style={styles.enableButton}
            onPress={() => void enableLocation()}
            disabled={permission === "requesting"}
          >
            <Text style={styles.enableText}>
              {permission === "requesting" ? "Locating…" : "Enable"}
            </Text>
          </Pressable>
        )}
      </View>

      <Text style={styles.label}>Current location</Text>
      <Text style={styles.card}>{locationLabel}</Text>

      <Text style={styles.label}>Origin</Text>
      <TextInput style={styles.input} value={origin} onChangeText={setOrigin} />
      <Text style={styles.label}>Destination</Text>
      <TextInput style={styles.input} value={destination} onChangeText={setDestination} />

      {notice ? <Text style={styles.notice}>{notice}</Text> : null}

      <Pressable style={styles.primary} onPress={() => void startSafeRoute()} disabled={searching}>
        {searching ? (
          <ActivityIndicator color="white" />
        ) : (
          <Text style={styles.white}>Start SafeRoute</Text>
        )}
      </Pressable>
      <Link href="/report" style={styles.secondary}>
        Report incident
      </Link>
      <Link href="/sos" style={styles.sos}>
        Emergency SOS
      </Link>
      <Text style={styles.note}>
        Scores are decision-support estimates and do not guarantee safety.
      </Text>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, padding: 24, backgroundColor: "#f5f7f8" },
  authRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 35,
  },
  authText: { fontSize: 12, color: "#66737d" },
  authLink: { fontSize: 12, color: "#1769aa", fontWeight: "700" },
  eyebrow: { color: "#1769aa", fontWeight: "700", fontSize: 11, marginTop: 10 },
  title: { fontSize: 28, fontWeight: "700", marginVertical: 14 },
  score: {
    backgroundColor: "#e5f4eb",
    padding: 22,
    borderRadius: 10,
    marginBottom: 16,
  },
  scoreNumber: { fontSize: 46, fontWeight: "800", color: "#178652" },
  permissionCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: "#c9dbe8",
    borderRadius: 9,
    backgroundColor: "#eef6fb",
  },
  permissionCopy: { flex: 1 },
  permissionTitle: { fontWeight: "700", color: "#14212b" },
  permissionText: {
    marginTop: 3,
    color: "#66737d",
    fontSize: 11,
    lineHeight: 16,
  },
  enableButton: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 6,
    backgroundColor: "#1769aa",
  },
  enableText: { color: "white", fontWeight: "700" },
  label: { color: "#66737d", marginTop: 14 },
  card: {
    backgroundColor: "white",
    padding: 18,
    borderRadius: 8,
    marginTop: 5,
  },
  input: {
    backgroundColor: "white",
    borderWidth: 1,
    borderColor: "#ccd4d8",
    padding: 12,
    marginTop: 5,
    borderRadius: 8,
  },
  notice: { fontSize: 12, color: "#9a6b12", marginTop: 12 },
  primary: {
    backgroundColor: "#1769aa",
    padding: 16,
    borderRadius: 7,
    alignItems: "center",
    marginTop: 20,
  },
  white: { color: "white", fontWeight: "700" },
  secondary: { padding: 16, textAlign: "center", color: "#1769aa" },
  sos: {
    padding: 16,
    textAlign: "center",
    color: "#c33d3d",
    fontWeight: "700",
  },
  note: { fontSize: 11, color: "#66737d", marginTop: 20 },
});
