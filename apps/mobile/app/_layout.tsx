import { Stack } from "expo-router";
import { useEffect } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { useSessionStore } from "../lib/session-store";

export default function Layout() {
  const hydrated = useSessionStore((state) => state.hydrated);
  const hydrate = useSessionStore((state) => state.hydrate);

  useEffect(() => {
    void hydrate();
  }, [hydrate]);

  if (!hydrated) {
    return (
      <View accessibilityLabel="Restoring your secure session" style={styles.loading}>
        <View style={styles.mark}><View style={styles.dot} /></View>
        <Text style={styles.brand}>ROADSIGNAL</Text>
        <ActivityIndicator color="#FFDA00" style={styles.spinner} />
      </View>
    );
  }

  return (
    <Stack screenOptions={{ headerTintColor: "#1769aa" }}>
      <Stack.Screen name="login" options={{ headerShown: false }} />
    </Stack>
  );
}

const styles = StyleSheet.create({
  loading: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#06171D" },
  mark: { width: 34, height: 34, borderRadius: 17, alignItems: "center", justifyContent: "center", backgroundColor: "#FFDA00" },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: "#08232B" },
  brand: { marginTop: 12, color: "#FFFFFF", fontSize: 18, fontWeight: "900", letterSpacing: -0.3 },
  spinner: { marginTop: 24 },
});
