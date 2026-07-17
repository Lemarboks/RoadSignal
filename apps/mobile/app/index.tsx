import * as Location from "expo-location";
import { Link } from "expo-router";
import { useState } from "react";
import { Pressable, SafeAreaView, StyleSheet, Text, View } from "react-native";

type PermissionState = "unknown" | "requesting" | "granted" | "denied";

export default function Home() {
  const [permission, setPermission] = useState<PermissionState>("unknown");
  const [locationLabel, setLocationLabel] = useState(
    "Cape Town CBD · simulation",
  );

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

  return (
    <SafeAreaView style={styles.page}>
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
      <Text style={styles.label}>Recent alerts</Text>
      <Text style={styles.card}>Broken traffic light · 1.2 km away</Text>
      <Link href="/trip" asChild>
        <Pressable style={styles.primary}>
          <Text style={styles.white}>Start SafeRoute</Text>
        </Pressable>
      </Link>
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
  eyebrow: { color: "#1769aa", fontWeight: "700", fontSize: 11, marginTop: 35 },
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
  primary: {
    backgroundColor: "#1769aa",
    padding: 16,
    borderRadius: 7,
    alignItems: "center",
    marginTop: 28,
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
