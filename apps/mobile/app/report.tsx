import { useState } from "react";
import * as SecureStore from "expo-secure-store";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { ApiError } from "../lib/api-client";
import { apiClient } from "../lib/session-store";

const PENDING_REPORT_KEY = "roadsignal.mobile.pending-report.v1";

export default function Report() {
  const [incidentType, setIncidentType] = useState("Accident");
  const [severity, setSeverity] = useState("3");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState("");

  async function submit() {
    setSubmitting(true);
    setStatus("");
    const report = {
      incident_type: incidentType,
      severity: Math.min(5, Math.max(1, Number(severity) || 1)),
      description,
      location: { latitude: -33.9249, longitude: 18.4241 },
    };
    await SecureStore.setItemAsync(PENDING_REPORT_KEY, JSON.stringify(report));
    try {
      await apiClient.request("/api/v1/incidents", {
        method: "POST",
        body: JSON.stringify(report),
      });
      await SecureStore.deleteItemAsync(PENDING_REPORT_KEY);
      setStatus("Report submitted. It begins unverified with a confidence estimate.");
      setDescription("");
    } catch (err) {
      setStatus(
        err instanceof ApiError && err.status === 401
          ? "Sign in to submit a report."
          : err instanceof ApiError
            ? err.message
            : "The report service is unavailable. This report is secured on your device; press submit to retry.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <View style={s.page}>
      <Text style={s.title}>Report incident</Text>
      <Text>Type</Text>
      <TextInput style={s.input} value={incidentType} onChangeText={setIncidentType} />
      <Text>Severity (1–5)</Text>
      <TextInput
        style={s.input}
        value={severity}
        onChangeText={setSeverity}
        keyboardType="number-pad"
      />
      <Text>Location</Text>
      <TextInput style={s.input} value="Current simulated location" editable={false} />
      <Text>Description</Text>
      <TextInput
        style={[s.input, { height: 100 }]}
        multiline
        placeholder="What did you observe?"
        value={description}
        onChangeText={setDescription}
      />
      {status ? <Text style={s.status}>{status}</Text> : null}
      <Pressable style={s.button} onPress={() => void submit()} disabled={submitting}>
        {submitting ? (
          <ActivityIndicator color="white" />
        ) : (
          <Text style={{ color: "white" }}>Submit unverified report</Text>
        )}
      </Pressable>
      <Text style={s.note}>
        Reports begin unverified with a confidence estimate and can be confirmed or disputed.
      </Text>
    </View>
  );
}

const s = StyleSheet.create({
  page: { flex: 1, padding: 24, backgroundColor: "#f5f7f8" },
  title: { fontSize: 28, fontWeight: "700", marginBottom: 25 },
  input: {
    backgroundColor: "white",
    borderWidth: 1,
    borderColor: "#ccd4d8",
    padding: 12,
    marginVertical: 7,
    borderRadius: 6,
  },
  status: { color: "#1769aa", marginTop: 6 },
  button: { backgroundColor: "#1769aa", padding: 15, alignItems: "center", marginTop: 15 },
  note: { fontSize: 12, color: "#66737d", marginTop: 15 },
});
