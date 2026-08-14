import { router } from "expo-router";
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
import { ApiError } from "../lib/api-client";
import { apiClient, useSessionStore } from "../lib/session-store";

export default function Login() {
  const setSession = useSessionStore((state) => state.setSession);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setLoading(true);
    setError("");
    try {
      const session =
        mode === "login"
          ? await apiClient.login(email, password)
          : await apiClient.register(name, email, password);
      setSession(session);
      router.back();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The service is unavailable.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={s.page}>
      <Text style={s.title}>{mode === "login" ? "Sign in" : "Create account"}</Text>
      <Text style={s.note}>
        Tokens stay in memory on this device and are cleared when the app restarts.
      </Text>
      {mode === "register" && (
        <TextInput
          style={s.input}
          placeholder="Name"
          value={name}
          onChangeText={setName}
          autoCapitalize="words"
        />
      )}
      <TextInput
        style={s.input}
        placeholder="Email"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
      />
      <TextInput
        style={s.input}
        placeholder="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />
      {error ? <Text style={s.error}>{error}</Text> : null}
      <Pressable style={s.primary} onPress={() => void submit()} disabled={loading}>
        {loading ? (
          <ActivityIndicator color="white" />
        ) : (
          <Text style={s.white}>{mode === "login" ? "Sign in" : "Register"}</Text>
        )}
      </Pressable>
      <Pressable onPress={() => setMode(mode === "login" ? "register" : "login")}>
        <Text style={s.link}>
          {mode === "login" ? "Need an account? Register" : "Have an account? Sign in"}
        </Text>
      </Pressable>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  page: { flex: 1, padding: 24, justifyContent: "center", backgroundColor: "#f5f7f8" },
  title: { fontSize: 28, fontWeight: "700", marginBottom: 6 },
  note: { fontSize: 12, color: "#66737d", marginBottom: 20 },
  input: {
    backgroundColor: "white",
    borderWidth: 1,
    borderColor: "#ccd4d8",
    padding: 14,
    marginVertical: 6,
    borderRadius: 8,
  },
  error: { color: "#c33d3d", marginTop: 6 },
  primary: {
    backgroundColor: "#1769aa",
    padding: 16,
    borderRadius: 8,
    alignItems: "center",
    marginTop: 16,
  },
  white: { color: "white", fontWeight: "700" },
  link: { color: "#1769aa", textAlign: "center", marginTop: 16 },
});
